import logging
from typing import Any, Protocol

from querya.agent.models import AgentResult

logger = logging.getLogger(__name__)


class TraceExporter(Protocol):
    def export(self, run_id: str, result: AgentResult, *, model: str) -> None: ...


class LangfuseExporter:
    """Mirrors finished runs to Langfuse. Credentials come from the usual LANGFUSE_* env vars."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            try:
                from langfuse import get_client
            except ImportError as exc:
                raise RuntimeError(
                    "Langfuse export is enabled but the package is missing; "
                    "install with `uv sync --extra langfuse`"
                ) from exc
            client = get_client()
        self._client = client

    def export(self, run_id: str, result: AgentResult, *, model: str) -> None:
        try:
            self._export(run_id, result, model)
        except Exception:
            # Tracing must never break a user request.
            logger.exception("langfuse export failed for run %s", run_id)

    def _export(self, run_id: str, result: AgentResult, model: str) -> None:
        root = self._client.start_observation(
            name="querya.ask",
            as_type="agent",
            input={"question": result.question},
            output={"answer": result.answer, "sql": result.sql, "row_count": result.row_count},
            metadata={"run_id": run_id, "status": result.status, "latency_ms": result.latency_ms},
            level="ERROR" if result.status == "failed" else "DEFAULT",
            status_message=result.error,
        )
        for step in result.steps:
            output = step.output
            if step.text is not None:
                output = {"text": step.text, **_as_dict(step.output)}
            common: dict[str, Any] = {
                "name": step.name,
                "input": step.input,
                "output": output,
                "metadata": {"index": step.index, "sql": step.sql, "latency_ms": step.latency_ms},
                "level": "ERROR" if step.status == "error" else "DEFAULT",
            }
            if step.kind == "llm":
                usage = None
                if step.input_tokens is not None:
                    usage = {"input": step.input_tokens, "output": step.output_tokens or 0}
                child = root.start_observation(
                    as_type="generation", model=model, usage_details=usage, **common
                )
            else:
                child = root.start_observation(as_type="tool", **common)
            child.end()
        root.end()
        self._client.flush()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {} if value is None else {"output": value}
