from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field

StepKind = Literal["llm", "tool", "answer", "error"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    # SQLite drops the offset on round-trip; everything is stored in UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


UtcDatetime = Annotated[datetime, AfterValidator(_ensure_utc)]


class Step(BaseModel):
    index: int
    kind: StepKind
    name: str
    status: Literal["ok", "error"] = "ok"
    text: str | None = None
    input: dict[str, Any] | None = None
    output: Any = None
    sql: str | None = None
    row_count: int | None = None
    latency_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    started_at: UtcDatetime = Field(default_factory=utcnow)


class AgentResult(BaseModel):
    status: Literal["succeeded", "failed"]
    question: str
    answer: str | None = None
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str | None = None
    steps: list[Step] = Field(default_factory=list)
    llm_calls: int = 0
    sql_attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
