from pathlib import Path
from typing import Any

from querya.agent import AgentResult, Step
from querya.tracing import LangfuseExporter, TraceStore


def _result() -> AgentResult:
    return AgentResult(
        status="succeeded",
        question="Revenue in 2025?",
        answer="About 6.2M.",
        sql="SELECT 1",
        columns=["revenue"],
        rows=[[6244558.88]],
        row_count=1,
        steps=[
            Step(index=0, kind="tool", name="list_tables", output="tables"),
            Step(
                index=1,
                kind="llm",
                name="model",
                text="thinking",
                output={"tool_calls": []},
                input_tokens=10,
                output_tokens=2,
            ),
            Step(index=2, kind="tool", name="run_sql", status="error", output="Database error"),
        ],
        llm_calls=1,
        sql_attempts=1,
    )


def test_store_round_trip(tmp_path: Path) -> None:
    store = TraceStore(f"sqlite:///{(tmp_path / 'nested' / 'traces.db').as_posix()}")
    run_id = store.create_run("Revenue in 2025?", provider="fake", model="m")
    assert store.get_run(run_id).status == "running"  # type: ignore[union-attr]

    result = _result()
    for step in result.steps:
        store.add_step(run_id, step)
    store.finish_run(run_id, result)

    detail = store.get_run(run_id)
    assert detail is not None
    assert detail.status == "succeeded"
    assert detail.rows == [[6244558.88]]
    assert [s.name for s in detail.steps] == ["list_tables", "model", "run_sql"]
    assert detail.steps[1].output == {"tool_calls": []}
    assert detail.finished_at is not None
    assert detail.created_at.tzinfo is not None
    assert store.count_runs() == 1
    store.close()


def test_fail_run_marks_status(tmp_path: Path) -> None:
    store = TraceStore(f"sqlite:///{(tmp_path / 'traces.db').as_posix()}")
    run_id = store.create_run("q", provider="fake", model="m")
    store.fail_run(run_id, "Cancelled by the client")
    run = store.get_run(run_id)
    assert run is not None
    assert (run.status, run.error) == ("failed", "Cancelled by the client")
    store.close()


class _FakeObservation:
    def __init__(self, log: list[dict[str, Any]], **kwargs: Any) -> None:
        self.log = log
        self.kwargs = kwargs
        self.ended = False
        log.append(kwargs)

    def start_observation(self, **kwargs: Any) -> "_FakeObservation":
        return _FakeObservation(self.log, **kwargs)

    def end(self) -> None:
        self.ended = True


class _FakeLangfuse:
    def __init__(self) -> None:
        self.log: list[dict[str, Any]] = []
        self.flushed = False

    def start_observation(self, **kwargs: Any) -> _FakeObservation:
        return _FakeObservation(self.log, **kwargs)

    def flush(self) -> None:
        self.flushed = True


def test_langfuse_exporter_maps_steps_to_observations() -> None:
    fake = _FakeLangfuse()
    LangfuseExporter(client=fake).export("run-1", _result(), model="qwen")
    root, *children = fake.log
    assert root["as_type"] == "agent"
    assert root["metadata"]["run_id"] == "run-1"
    assert [c["as_type"] for c in children] == ["tool", "generation", "tool"]
    assert children[1]["usage_details"] == {"input": 10, "output": 2}
    assert children[1]["model"] == "qwen"
    assert children[2]["level"] == "ERROR"
    assert fake.flushed


def test_langfuse_errors_never_escape() -> None:
    class Broken:
        def start_observation(self, **_: Any) -> None:
            raise ConnectionError("langfuse down")

    LangfuseExporter(client=Broken()).export("run-1", _result(), model="m")
