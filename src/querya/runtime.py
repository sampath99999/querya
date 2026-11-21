from dataclasses import dataclass

from sqlalchemy import Engine

from querya.agent import SQLAgent, Toolbox
from querya.agent.prompts import load_glossary
from querya.config import Settings
from querya.db import QueryRunner, SchemaCatalog, create_readonly_engine
from querya.llm import LLMClient, build_llm_client
from querya.sql_guard import SQLGuard


@dataclass
class Runtime:
    settings: Settings
    engine: Engine
    catalog: SchemaCatalog
    toolbox: Toolbox
    llm: LLMClient
    agent: SQLAgent

    def close(self) -> None:
        self.engine.dispose()


def build_runtime(settings: Settings, llm: LLMClient | None = None) -> Runtime:
    engine = create_readonly_engine(settings.database_url)
    catalog = SchemaCatalog(engine)
    runner = QueryRunner(
        engine, timeout_ms=settings.statement_timeout_ms, max_rows=settings.max_rows
    )
    guard = SQLGuard(
        engine.dialect.name, max_rows=settings.max_rows, allowed_tables=catalog.table_names
    )
    toolbox = Toolbox(catalog, runner, guard)
    llm = llm or build_llm_client(settings)
    agent = SQLAgent(
        llm,
        toolbox,
        max_steps=settings.max_steps,
        max_sql_retries=settings.max_sql_retries,
        glossary=load_glossary(settings.glossary_path),
    )
    return Runtime(
        settings=settings, engine=engine, catalog=catalog, toolbox=toolbox, llm=llm, agent=agent
    )
