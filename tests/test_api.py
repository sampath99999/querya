import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from querya.agent import AgentResult
from querya.api import create_app
from querya.config import Settings
from tests.fakes import ScriptedLLM, final_answer, run_sql

SQL = "SELECT channel, COUNT(*) AS orders FROM orders GROUP BY channel ORDER BY channel"


class RecordingExporter:
    def __init__(self) -> None:
        self.exported: list[tuple[str, AgentResult]] = []

    def export(self, run_id: str, result: AgentResult, *, model: str) -> None:
        self.exported.append((run_id, result))


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM([run_sql(SQL), final_answer("Web is the biggest channel.")])


@pytest.fixture
def exporter() -> RecordingExporter:
    return RecordingExporter()


@pytest.fixture
def client(
    settings: Settings, llm: ScriptedLLM, exporter: RecordingExporter
) -> Iterator[TestClient]:
    app = create_app(settings, llm=llm, exporters=[exporter], serve_frontend=False)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body == {
        "status": "ok",
        "database": "sqlite",
        "tables": 6,
        "provider": "fake",
        "model": "scripted",
    }


def test_schema_lists_tables_with_columns(client: TestClient) -> None:
    body = client.get("/schema").json()
    assert body["dialect"] == "sqlite"
    names = [t["name"] for t in body["tables"]]
    assert "orders" in names
    orders = next(t for t in body["tables"] if t["name"] == "orders")
    assert any(c["name"] == "order_date" for c in orders["columns"])


def test_ask_streams_steps_and_persists_the_run(
    client: TestClient, exporter: RecordingExporter
) -> None:
    response = client.post("/ask", json={"question": "Orders by channel?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "run"
    assert names[-1] == "result"
    assert names.count("step") == 5

    run_id = events[0][1]["run_id"]
    result = events[-1][1]
    assert result["run_id"] == run_id
    assert result["status"] == "succeeded"
    assert result["answer"] == "Web is the biggest channel."
    assert result["columns"] == ["channel", "orders"]
    assert [r[0] for r in result["rows"]] == ["mobile", "store", "web"]

    detail = client.get(f"/runs/{run_id}").json()
    assert detail["status"] == "succeeded"
    assert detail["question"] == "Orders by channel?"
    assert detail["sql"].startswith("SELECT channel")
    assert detail["rows"] == result["rows"]
    assert [s["name"] for s in detail["steps"]] == [
        "list_tables",
        "model",
        "run_sql",
        "model",
        "final_answer",
    ]
    sql_step = detail["steps"][2]
    assert sql_step["row_count"] == 3
    assert sql_step["latency_ms"] >= 0
    assert detail["steps"][1]["input_tokens"] == 100
    assert detail["created_at"].endswith(("Z", "+00:00"))

    runs = client.get("/runs").json()
    assert runs["total"] == 1
    assert runs["items"][0]["id"] == run_id
    assert runs["items"][0]["llm_calls"] == 2

    assert [run for run, _ in exporter.exported] == [run_id]


def test_failed_run_is_recorded(client: TestClient, llm: ScriptedLLM) -> None:
    llm.script = []
    events = parse_sse(client.post("/ask", json={"question": "Anything?"}).text)
    result = events[-1][1]
    assert result["status"] == "failed"
    assert result["error"] == "script exhausted"
    detail = client.get(f"/runs/{result['run_id']}").json()
    assert detail["status"] == "failed"
    assert detail["steps"][-1]["kind"] == "error"


def test_ask_validates_the_question(client: TestClient) -> None:
    assert client.post("/ask", json={"question": "  "}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 501}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/runs/does-not-exist").status_code == 404


def test_runs_pagination_bounds(client: TestClient) -> None:
    assert client.get("/runs?limit=0").status_code == 422
    assert client.get("/runs?limit=500").status_code == 422
    assert client.get("/runs?limit=5&offset=0").json() == {"items": [], "total": 0}
