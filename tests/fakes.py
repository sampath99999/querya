from collections.abc import Callable, Sequence
from itertools import count
from typing import Any

from querya.llm import ChatMessage, LLMError, LLMResponse, ToolCall, ToolSpec, Usage

ScriptItem = LLMResponse | Exception | Callable[[Sequence[ChatMessage]], LLMResponse]

_ids = count(1)


def tool_call(name: str, **arguments: Any) -> LLMResponse:
    return LLMResponse(
        tool_calls=[ToolCall(id=f"call_{next(_ids)}", name=name, arguments=arguments)],
        usage=Usage(input_tokens=100, output_tokens=20),
        model="scripted",
    )


def run_sql(sql: str) -> LLMResponse:
    return tool_call("run_sql", sql=sql)


def final_answer(answer: str) -> LLMResponse:
    return tool_call("final_answer", answer=answer)


def text(content: str) -> LLMResponse:
    return LLMResponse(
        text=content, usage=Usage(input_tokens=50, output_tokens=10), model="scripted"
    )


class ScriptedLLM:
    """Plays back a fixed list of responses and records what the agent sent."""

    provider = "fake"
    model = "scripted"

    def __init__(self, script: Sequence[ScriptItem]) -> None:
        self.script = list(script)
        self.calls: list[list[ChatMessage]] = []
        self.systems: list[str] = []

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        self.calls.append([m.model_copy(deep=True) for m in messages])
        self.systems.append(system)
        if not self.script:
            raise LLMError("script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(messages)
        return item
