import logging
import operator
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from querya.agent import prompts
from querya.agent.models import AgentResult, Step
from querya.agent.tools import FINAL_ANSWER, RUN_SQL, TOOL_SPECS, Toolbox
from querya.db import QueryResult
from querya.llm import ChatMessage, LLMClient, LLMError

logger = logging.getLogger(__name__)

MAX_NUDGES = 2
MAX_TRACE_OUTPUT_CHARS = 4_000


class AgentState(TypedDict, total=False):
    question: str
    messages: Annotated[list[ChatMessage], operator.add]
    steps: Annotated[list[Step], operator.add]
    llm_calls: int
    sql_attempts: int
    sql_errors: int
    nudges: int
    last_sql: str | None
    last_result: QueryResult | None
    answer: str | None
    error: str | None


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _clip(text: str, limit: int = MAX_TRACE_OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} more chars]"


class SQLAgent:
    """Plan -> write SQL -> run -> fix on error -> answer, as a LangGraph state machine."""

    def __init__(
        self,
        llm: LLMClient,
        toolbox: Toolbox,
        *,
        max_steps: int = 12,
        max_sql_retries: int = 3,
        glossary: str | None = None,
    ) -> None:
        self.llm = llm
        self.toolbox = toolbox
        self.max_steps = max_steps
        self.max_sql_retries = max_sql_retries
        self.system_prompt = prompts.build_system_prompt(
            toolbox.dialect, glossary if glossary is not None else prompts.load_glossary()
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(AgentState)
        graph.add_node("discover", self._discover)
        graph.add_node("model", self._call_model)
        graph.add_node("tools", self._run_tools)
        graph.add_node("fail", self._fail)
        graph.add_edge(START, "discover")
        graph.add_edge("discover", "model")
        graph.add_conditional_edges(
            "model", self._route_after_model, ["tools", "model", "fail", END]
        )
        graph.add_conditional_edges("tools", self._route_after_tools, ["model", "fail", END])
        graph.add_edge("fail", END)
        return graph.compile()

    async def _discover(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        outcome = self.toolbox.list_tables()
        step = Step(
            index=0,
            kind="tool",
            name="list_tables",
            output=outcome.content,
            latency_ms=_elapsed_ms(started),
        )
        message = ChatMessage(
            role="user",
            content=prompts.build_question_message(state["question"], outcome.content),
        )
        return {"messages": [message], "steps": [step]}

    async def _call_model(self, state: AgentState) -> dict[str, Any]:
        index = len(state.get("steps", []))
        llm_calls = state.get("llm_calls", 0)
        if llm_calls >= self.max_steps:
            return {"error": f"Stopped after {llm_calls} model calls without a final answer"}

        started = time.perf_counter()
        try:
            response = await self.llm.complete(
                system=self.system_prompt, messages=state["messages"], tools=TOOL_SPECS
            )
        except LLMError as exc:
            return {"error": str(exc), "llm_calls": llm_calls + 1}

        step = Step(
            index=index,
            kind="llm",
            name="model",
            text=response.reasoning or response.text or None,
            output={"tool_calls": [c.model_dump() for c in response.tool_calls]},
            latency_ms=_elapsed_ms(started),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        update: dict[str, Any] = {"llm_calls": llm_calls + 1, "steps": [step], "messages": []}
        if response.text or response.tool_calls:
            update["messages"].append(response.to_message())
        if response.tool_calls:
            return update

        # The model replied in prose. Accept it as the answer only if it has seen a result.
        if state.get("last_result") is not None and response.text:
            update["answer"] = response.text
            update["steps"].append(self._answer_step(index + 1, response.text, state))
            return update
        nudges = state.get("nudges", 0)
        if nudges >= MAX_NUDGES:
            update["error"] = "The model stopped without producing an answer"
            return update
        nudge = prompts.NUDGE_FINISH if state.get("last_result") else prompts.NUDGE_USE_TOOLS
        update["messages"].append(ChatMessage(role="user", content=nudge))
        update["nudges"] = nudges + 1
        return update

    async def _run_tools(self, state: AgentState) -> dict[str, Any]:
        assistant = state["messages"][-1]
        index = len(state.get("steps", []))
        steps: list[Step] = []
        messages: list[ChatMessage] = []
        sql_attempts = state.get("sql_attempts", 0)
        sql_errors = state.get("sql_errors", 0)
        last_sql = state.get("last_sql")
        last_result = state.get("last_result")
        answer: str | None = None
        ran_sql_this_turn = False

        for call in assistant.tool_calls:
            started = time.perf_counter()
            if call.name == FINAL_ANSWER:
                text = str(call.arguments.get("answer") or "").strip()
                reason = None
                if not text:
                    reason = "final_answer needs a non-empty 'answer'."
                elif last_result is None:
                    reason = "No query has succeeded yet. Call run_sql first."
                elif ran_sql_this_turn:
                    reason = "Wait for the run_sql result before calling final_answer."
                if reason:
                    steps.append(
                        Step(
                            index=index + len(steps),
                            kind="tool",
                            name=FINAL_ANSWER,
                            status="error",
                            input=call.arguments,
                            output=reason,
                        )
                    )
                    messages.append(
                        ChatMessage(
                            role="tool", tool_call_id=call.id, content=reason, is_error=True
                        )
                    )
                    continue
                answer = text
                messages.append(ChatMessage(role="tool", tool_call_id=call.id, content="ok"))
                continue

            outcome = await self.toolbox.call(call.name, call.arguments)
            if call.name == RUN_SQL:
                sql_attempts += 1
                ran_sql_this_turn = True
                if outcome.is_error:
                    sql_errors += 1
                else:
                    last_sql, last_result = outcome.sql, outcome.result
            steps.append(
                Step(
                    index=index + len(steps),
                    kind="tool",
                    name=call.name,
                    status="error" if outcome.is_error else "ok",
                    input=call.arguments,
                    output=_clip(outcome.content),
                    sql=outcome.sql,
                    row_count=outcome.result.row_count if outcome.result else None,
                    latency_ms=_elapsed_ms(started),
                )
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    tool_call_id=call.id,
                    content=outcome.content,
                    is_error=outcome.is_error,
                )
            )

        update: dict[str, Any] = {
            "steps": steps,
            "messages": messages,
            "sql_attempts": sql_attempts,
            "sql_errors": sql_errors,
            "last_sql": last_sql,
            "last_result": last_result,
        }
        if answer is not None:
            update["answer"] = answer
            final_state: AgentState = {**state, "last_sql": last_sql, "last_result": last_result}
            update["steps"].append(self._answer_step(index + len(steps), answer, final_state))
        return update

    def _answer_step(self, index: int, answer: str, state: AgentState) -> Step:
        result = state.get("last_result")
        return Step(
            index=index,
            kind="answer",
            name=FINAL_ANSWER,
            text=answer,
            sql=state.get("last_sql"),
            row_count=result.row_count if result else None,
        )

    async def _fail(self, state: AgentState) -> dict[str, Any]:
        error = state.get("error")
        if not error and state.get("sql_errors", 0) > self.max_sql_retries:
            error = f"Gave up after {state['sql_errors']} failed queries"
        if not error:
            error = f"Stopped after {state.get('llm_calls', 0)} model calls without an answer"
        step = Step(
            index=len(state.get("steps", [])),
            kind="error",
            name="agent",
            status="error",
            text=error,
        )
        return {"error": error, "steps": [step]}

    def _route_after_model(self, state: AgentState) -> str:
        if state.get("error"):
            return "fail"
        if state.get("answer"):
            return END
        last = state["messages"][-1]
        if last.role == "assistant" and last.tool_calls:
            return "tools"
        return "model"

    def _route_after_tools(self, state: AgentState) -> str:
        if state.get("answer"):
            return END
        if state.get("sql_errors", 0) > self.max_sql_retries:
            return "fail"
        if state.get("llm_calls", 0) >= self.max_steps:
            return "fail"
        return "model"

    async def stream(self, question: str) -> AsyncIterator[Step | AgentResult]:
        started = time.perf_counter()
        initial: AgentState = {"question": question, "messages": [], "steps": []}
        final: AgentState = initial
        config = {"recursion_limit": self.max_steps * 3 + 10}
        async for mode, chunk in self.graph.astream(
            initial, config=config, stream_mode=["updates", "values"]
        ):
            if mode == "values":
                final = chunk
                continue
            for delta in chunk.values():
                for step in (delta or {}).get("steps", []):
                    yield step
        yield self._build_result(question, final, _elapsed_ms(started))

    async def run(self, question: str) -> AgentResult:
        result: AgentResult | None = None
        async for item in self.stream(question):
            if isinstance(item, AgentResult):
                result = item
        assert result is not None
        return result

    def _build_result(self, question: str, state: AgentState, latency_ms: float) -> AgentResult:
        steps = state.get("steps", [])
        last = state.get("last_result")
        answer = state.get("answer")
        return AgentResult(
            status="succeeded" if answer else "failed",
            question=question,
            answer=answer,
            sql=state.get("last_sql"),
            columns=last.columns if last else [],
            rows=last.rows if last else [],
            row_count=last.row_count if last else 0,
            truncated=last.truncated if last else False,
            error=None if answer else state.get("error"),
            steps=steps,
            llm_calls=state.get("llm_calls", 0),
            sql_attempts=state.get("sql_attempts", 0),
            input_tokens=sum(s.input_tokens or 0 for s in steps),
            output_tokens=sum(s.output_tokens or 0 for s in steps),
            latency_ms=latency_ms,
        )
