import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    make_url,
    select,
    update,
)

from querya.agent.models import AgentResult, Step, UtcDatetime, utcnow

MAX_STORED_ROWS = 500

metadata = MetaData()

runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("question", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("answer", Text),
    Column("sql", Text),
    Column("columns", JSON),
    Column("rows", JSON),
    Column("row_count", Integer, nullable=False, default=0),
    Column("truncated", Boolean, nullable=False, default=False),
    Column("error", Text),
    Column("provider", String(32), nullable=False),
    Column("model", String(128), nullable=False),
    Column("llm_calls", Integer, nullable=False, default=0),
    Column("sql_attempts", Integer, nullable=False, default=0),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("latency_ms", Float, nullable=False, default=0.0),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("finished_at", DateTime(timezone=True)),
)

steps = Table(
    "steps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), ForeignKey("runs.id", ondelete="CASCADE"), index=True),
    Column("idx", Integer, nullable=False),
    Column("kind", String(16), nullable=False),
    Column("name", String(64), nullable=False),
    Column("status", String(8), nullable=False),
    Column("text", Text),
    Column("input", JSON),
    Column("output", JSON),
    Column("sql", Text),
    Column("row_count", Integer),
    Column("latency_ms", Float, nullable=False, default=0.0),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("started_at", DateTime(timezone=True), nullable=False),
)

RunStatus = Literal["running", "succeeded", "failed"]


class RunSummary(BaseModel):
    id: str
    question: str
    status: RunStatus
    answer: str | None
    row_count: int
    provider: str
    model: str
    llm_calls: int
    sql_attempts: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    created_at: UtcDatetime


class RunDetail(RunSummary):
    sql: str | None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    truncated: bool
    error: str | None
    finished_at: UtcDatetime | None
    steps: list[Step] = Field(default_factory=list)


class TraceStore:
    """Persists every agent run and its steps so they can be inspected later."""

    def __init__(self, database_url: str) -> None:
        url = make_url(database_url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url)
        metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def create_run(self, question: str, *, provider: str, model: str) -> str:
        run_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                insert(runs).values(
                    id=run_id,
                    question=question,
                    status="running",
                    provider=provider,
                    model=model,
                    created_at=utcnow(),
                )
            )
        return run_id

    def add_step(self, run_id: str, step: Step) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(steps).values(
                    run_id=run_id,
                    idx=step.index,
                    kind=step.kind,
                    name=step.name,
                    status=step.status,
                    text=step.text,
                    input=step.input,
                    output=step.output,
                    sql=step.sql,
                    row_count=step.row_count,
                    latency_ms=step.latency_ms,
                    input_tokens=step.input_tokens,
                    output_tokens=step.output_tokens,
                    started_at=step.started_at,
                )
            )

    def finish_run(self, run_id: str, result: AgentResult) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(
                    status=result.status,
                    answer=result.answer,
                    sql=result.sql,
                    columns=result.columns,
                    rows=result.rows[:MAX_STORED_ROWS],
                    row_count=result.row_count,
                    truncated=result.truncated or len(result.rows) > MAX_STORED_ROWS,
                    error=result.error,
                    llm_calls=result.llm_calls,
                    sql_attempts=result.sql_attempts,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    finished_at=utcnow(),
                )
            )

    def fail_run(self, run_id: str, error: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(status="failed", error=error, finished_at=utcnow())
            )

    def list_runs(self, *, limit: int = 50, offset: int = 0) -> list[RunSummary]:
        query = select(runs).order_by(runs.c.created_at.desc()).limit(limit).offset(offset)
        with self.engine.connect() as conn:
            return [RunSummary.model_validate(dict(r)) for r in conn.execute(query).mappings()]

    def count_runs(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(runs)).scalar_one())

    def get_run(self, run_id: str) -> RunDetail | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
            if row is None:
                return None
            step_rows = conn.execute(
                select(steps).where(steps.c.run_id == run_id).order_by(steps.c.idx, steps.c.id)
            ).mappings()
            trace = [Step.model_validate({**dict(s), "index": s["idx"]}) for s in step_rows]
        data = dict(row)
        data["columns"] = data["columns"] or []
        data["rows"] = data["rows"] or []
        return RunDetail.model_validate({**data, "steps": trace})
