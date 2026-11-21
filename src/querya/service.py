import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal

from pydantic import BaseModel

from querya.agent import AgentResult, SQLAgent, Step
from querya.tracing import TraceExporter, TraceStore

logger = logging.getLogger(__name__)

EventName = Literal["run", "step", "result", "error"]


class AskEvent(BaseModel):
    event: EventName
    data: dict[str, Any]


class AskService:
    """Runs the agent for one question and records every step as it happens."""

    def __init__(
        self,
        agent: SQLAgent,
        store: TraceStore,
        *,
        provider: str,
        model: str,
        exporters: Sequence[TraceExporter] = (),
    ) -> None:
        self.agent = agent
        self.store = store
        self.provider = provider
        self.model = model
        self.exporters = list(exporters)
        self._pending: set[asyncio.Task[None]] = set()

    async def stream(self, question: str) -> AsyncIterator[AskEvent]:
        run_id = await asyncio.to_thread(
            self.store.create_run, question, provider=self.provider, model=self.model
        )
        yield AskEvent(
            event="run",
            data={
                "run_id": run_id,
                "question": question,
                "provider": self.provider,
                "model": self.model,
            },
        )
        try:
            async for item in self.agent.stream(question):
                if isinstance(item, Step):
                    await asyncio.to_thread(self.store.add_step, run_id, item)
                    yield AskEvent(event="step", data=item.model_dump(mode="json"))
                    continue
                await asyncio.to_thread(self.store.finish_run, run_id, item)
                self._export(run_id, item)
                yield AskEvent(
                    event="result",
                    data={"run_id": run_id, **item.model_dump(mode="json", exclude={"steps"})},
                )
        except asyncio.CancelledError:
            self.store.fail_run(run_id, "Cancelled by the client")
            raise
        except Exception as exc:
            logger.exception("agent run %s crashed", run_id)
            message = f"Internal error: {type(exc).__name__}"
            await asyncio.to_thread(self.store.fail_run, run_id, message)
            yield AskEvent(event="error", data={"run_id": run_id, "error": message})

    async def ask(self, question: str) -> tuple[str, AgentResult | None]:
        run_id = ""
        result: AgentResult | None = None
        async for event in self.stream(question):
            if event.event == "run":
                run_id = event.data["run_id"]
            elif event.event == "result":
                result = AgentResult.model_validate(event.data)
        return run_id, result

    def _export(self, run_id: str, result: AgentResult) -> None:
        for exporter in self.exporters:
            task = asyncio.create_task(
                asyncio.to_thread(exporter.export, run_id, result, model=self.model)
            )
            self._pending.add(task)
            task.add_done_callback(self._on_export_done)

    def _on_export_done(self, task: asyncio.Task[None]) -> None:
        self._pending.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("trace export failed", exc_info=task.exception())
