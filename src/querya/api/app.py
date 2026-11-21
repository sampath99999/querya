import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles

from querya import __version__
from querya.api.schemas import AskRequest, HealthResponse, RunList, SchemaResponse
from querya.config import PROJECT_ROOT, Settings, get_settings
from querya.llm import LLMClient
from querya.logging_setup import configure_logging
from querya.runtime import Runtime, build_runtime
from querya.service import AskService
from querya.tracing import LangfuseExporter, RunDetail, TraceExporter, TraceStore

logger = logging.getLogger(__name__)

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

router = APIRouter()


def get_runtime(request: Request) -> Runtime:
    runtime: Runtime = request.app.state.runtime
    return runtime


def get_store(request: Request) -> TraceStore:
    store: TraceStore = request.app.state.store
    return store


def get_service(request: Request) -> AskService:
    service: AskService = request.app.state.service
    return service


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
StoreDep = Annotated[TraceStore, Depends(get_store)]
ServiceDep = Annotated[AskService, Depends(get_service)]


@router.get("/health")
def health(runtime: RuntimeDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        database=runtime.engine.dialect.name,
        tables=len(runtime.catalog.table_names),
        provider=runtime.llm.provider,
        model=runtime.llm.model,
    )


@router.get("/schema")
def schema(runtime: RuntimeDep) -> SchemaResponse:
    return SchemaResponse(dialect=runtime.engine.dialect.name, tables=runtime.catalog.all_tables())


@router.post("/ask", response_class=EventSourceResponse)
async def ask(body: AskRequest, service: ServiceDep) -> AsyncIterator[ServerSentEvent]:
    async for event in service.stream(body.question):
        yield ServerSentEvent(event=event.event, data=event.data)


@router.get("/runs")
async def list_runs(
    store: StoreDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunList:
    items, total = await asyncio.gather(
        asyncio.to_thread(store.list_runs, limit=limit, offset=offset),
        asyncio.to_thread(store.count_runs),
    )
    return RunList(items=items, total=total)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, store: StoreDep) -> RunDetail:
    run = await asyncio.to_thread(store.get_run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def create_app(
    settings: Settings | None = None,
    *,
    llm: LLMClient | None = None,
    exporters: list[TraceExporter] | None = None,
    serve_frontend: bool = True,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = build_runtime(settings, llm=llm)
        store = TraceStore(settings.trace_database_url)
        sinks = list(exporters) if exporters is not None else []
        if exporters is None and settings.langfuse_enabled:
            sinks.append(LangfuseExporter())
        app.state.runtime = runtime
        app.state.store = store
        app.state.service = AskService(
            runtime.agent,
            store,
            provider=runtime.llm.provider,
            model=runtime.llm.model,
            exporters=sinks,
        )
        logger.info(
            "querya ready: %s database, %d tables, %s/%s",
            runtime.engine.dialect.name,
            len(runtime.catalog.table_names),
            runtime.llm.provider,
            runtime.llm.model,
        )
        try:
            yield
        finally:
            runtime.close()
            store.close()

    app = FastAPI(title="Querya", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    if serve_frontend and FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


def app_factory() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    return create_app(settings)
