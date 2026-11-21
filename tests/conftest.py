from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from querya.agent import SQLAgent, Toolbox
from querya.config import Settings
from querya.db import QueryRunner, SchemaCatalog, create_readonly_engine
from querya.llm import LLMClient
from querya.seed import SeedConfig, generate, load_dataset
from querya.sql_guard import SQLGuard


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "retail.db"
    data = generate(SeedConfig(seed=7, customers=150, orders_per_day=2.0))
    load_dataset(f"sqlite:///{path.as_posix()}", data)
    return path


@pytest.fixture(scope="session")
def db_url(db_path: Path) -> str:
    return f"sqlite:///{db_path.as_posix()}"


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    eng = create_readonly_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def catalog(engine: Engine) -> SchemaCatalog:
    return SchemaCatalog(engine)


@pytest.fixture
def toolbox(engine: Engine, catalog: SchemaCatalog) -> Toolbox:
    runner = QueryRunner(engine, timeout_ms=2_000, max_rows=50)
    guard = SQLGuard("sqlite", max_rows=50, allowed_tables=catalog.table_names)
    return Toolbox(catalog, runner, guard, preview_rows=10)


@pytest.fixture
def make_agent(toolbox: Toolbox):  # type: ignore[no-untyped-def]
    def _make(llm: LLMClient, **kwargs: int) -> SQLAgent:
        return SQLAgent(llm, toolbox, glossary="- test glossary", **kwargs)

    return _make


@pytest.fixture
def settings(db_url: str, tmp_path: Path) -> Settings:
    return Settings(
        database_url=db_url,
        trace_database_url=f"sqlite:///{(tmp_path / 'traces.db').as_posix()}",
        max_rows=50,
        _env_file=None,  # type: ignore[call-arg]
    )
