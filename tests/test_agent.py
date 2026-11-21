from collections.abc import Callable

from querya.agent import AgentResult, SQLAgent, Step
from querya.llm import LLMClient, LLMError, LLMResponse, ToolCall, Usage
from tests.fakes import ScriptedLLM, final_answer, run_sql, text, tool_call

AgentFactory = Callable[..., SQLAgent]

GOOD_SQL = "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status ORDER BY 2 DESC"


async def test_happy_path_returns_answer_rows_and_sql(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM(
        [
            tool_call("describe_table", table="orders"),
            run_sql(GOOD_SQL),
            final_answer("Most orders are delivered."),
        ]
    )
    result = await make_agent(llm).run("How many orders per status?")

    assert result.status == "succeeded"
    assert result.answer == "Most orders are delivered."
    assert result.columns == ["status", "order_count"]
    assert result.rows[0][0] == "delivered"
    assert result.sql is not None
    assert result.sql.endswith("LIMIT 50")
    assert result.llm_calls == 3
    assert result.sql_attempts == 1
    assert result.input_tokens == 300
    assert [s.name for s in result.steps] == [
        "list_tables",
        "model",
        "describe_table",
        "model",
        "run_sql",
        "model",
        "final_answer",
    ]
    assert [s.index for s in result.steps] == list(range(7))


async def test_first_message_contains_question_and_tables(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([run_sql(GOOD_SQL), final_answer("done")])
    await make_agent(llm).run("Orders by status?")
    first = llm.calls[0][0]
    assert first.role == "user"
    assert "Question: Orders by status?" in first.content
    assert "- payments (" in first.content
    assert "sqlite" in llm.systems[0].lower()
    assert "test glossary" in llm.systems[0]


async def test_reads_the_error_and_fixes_the_query(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM(
        [
            run_sql("SELECT status, COUNT(*) FROM order GROUP BY status"),
            run_sql("SELECT order_status, COUNT(*) FROM orders GROUP BY 1"),
            run_sql(GOOD_SQL),
            final_answer("Fixed it."),
        ]
    )
    result = await make_agent(llm).run("Orders by status?")

    assert result.status == "succeeded"
    assert result.sql_attempts == 3
    sql_steps = [s for s in result.steps if s.name == "run_sql"]
    assert [s.status for s in sql_steps] == ["error", "error", "ok"]
    assert "no such column: order_status" in sql_steps[1].output

    # The model must have been shown each error as a tool result before retrying.
    second_call_tail = llm.calls[1][-1]
    assert second_call_tail.role == "tool"
    assert second_call_tail.is_error
    third_call_tail = llm.calls[2][-1]
    assert "no such column: order_status" in third_call_tail.content


async def test_guard_rejection_is_fed_back_and_counts_as_a_retry(
    make_agent: AgentFactory,
) -> None:
    llm = ScriptedLLM([run_sql("DROP TABLE orders"), run_sql(GOOD_SQL), final_answer("ok")])
    result = await make_agent(llm).run("Orders by status?")
    assert result.status == "succeeded"
    rejected = next(s for s in result.steps if s.name == "run_sql")
    assert rejected.status == "error"
    assert "Rejected by the SQL guard" in rejected.output


async def test_gives_up_after_max_sql_retries(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([run_sql("SELECT nope FROM orders")] * 5)
    result = await make_agent(llm, max_sql_retries=2).run("Broken question")
    assert result.status == "failed"
    assert result.error == "Gave up after 3 failed queries"
    assert result.sql_attempts == 3
    assert result.steps[-1].kind == "error"
    assert len(llm.calls) == 3


async def test_prose_reply_after_a_result_is_accepted_as_answer(
    make_agent: AgentFactory,
) -> None:
    llm = ScriptedLLM([run_sql(GOOD_SQL), text("There are 5 statuses.")])
    result = await make_agent(llm).run("Orders by status?")
    assert result.status == "succeeded"
    assert result.answer == "There are 5 statuses."
    assert result.steps[-1].kind == "answer"


async def test_prose_reply_without_sql_gets_a_nudge(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([text("I think it is about 100."), run_sql(GOOD_SQL), final_answer("ok")])
    result = await make_agent(llm).run("Orders by status?")
    assert result.status == "succeeded"
    nudge = llm.calls[1][-1]
    assert nudge.role == "user"
    assert "run_sql" in nudge.content


async def test_final_answer_before_any_query_is_refused(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([final_answer("Made up number"), run_sql(GOOD_SQL), final_answer("Real")])
    result = await make_agent(llm).run("Orders by status?")
    assert result.answer == "Real"
    refused = next(s for s in result.steps if s.name == "final_answer")
    assert refused.status == "error"


async def test_final_answer_in_same_turn_as_sql_must_wait(make_agent: AgentFactory) -> None:
    same_turn = LLMResponse(
        tool_calls=[
            ToolCall(id="a", name="run_sql", arguments={"sql": GOOD_SQL}),
            ToolCall(id="b", name="final_answer", arguments={"answer": "Guessing"}),
        ],
        usage=Usage(),
        model="scripted",
    )
    llm = ScriptedLLM([same_turn, final_answer("After seeing rows")])
    result = await make_agent(llm).run("Orders by status?")
    assert result.answer == "After seeing rows"
    tool_results = [m for m in llm.calls[1] if m.role == "tool"]
    assert [m.tool_call_id for m in tool_results] == ["a", "b"]
    assert tool_results[1].is_error


async def test_stops_at_max_steps(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([tool_call("list_tables")] * 10)
    result = await make_agent(llm, max_steps=3).run("Loop forever")
    assert result.status == "failed"
    assert result.llm_calls == 3
    assert "3 model calls" in (result.error or "")


async def test_llm_errors_fail_the_run_cleanly(make_agent: AgentFactory) -> None:
    llm = ScriptedLLM([LLMError("connection refused")])
    result = await make_agent(llm).run("Anything")
    assert result.status == "failed"
    assert result.error == "connection refused"
    assert result.steps[-1].kind == "error"


async def test_stream_yields_steps_then_result(make_agent: AgentFactory) -> None:
    llm: LLMClient = ScriptedLLM([run_sql(GOOD_SQL), final_answer("ok")])
    items = [item async for item in make_agent(llm).stream("Orders by status?")]
    assert all(isinstance(i, Step) for i in items[:-1])
    assert isinstance(items[-1], AgentResult)
    assert len(items[-1].steps) == len(items) - 1
