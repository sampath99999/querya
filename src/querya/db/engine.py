import datetime as dt
import logging
import sqlite3
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import URL, Engine, create_engine, event, make_url
from sqlalchemy.exc import DBAPIError, OperationalError

logger = logging.getLogger(__name__)

SQLITE_PROGRESS_OPS = 2_000


class DatabaseNotFoundError(RuntimeError):
    pass


class QueryTimeoutError(RuntimeError):
    pass


class QueryExecutionError(RuntimeError):
    pass


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: float


def _readonly_url(database_url: str) -> tuple[URL, dict[str, Any]]:
    url = make_url(database_url)
    backend = url.get_backend_name()
    if backend == "sqlite":
        if not url.database or url.database == ":memory:":
            raise ValueError("A file-backed SQLite database is required for read-only access")
        path = Path(url.database).expanduser().resolve()
        if not path.exists():
            raise DatabaseNotFoundError(f"SQLite database not found at {path}; run `querya seed`")
        ro = url.set(database=f"file:{path.as_posix()}", query={"mode": "ro", "uri": "true"})
        return ro, {"check_same_thread": False}
    if backend == "postgresql":
        options = "-c default_transaction_read_only=on"
        return url, {"options": options}
    raise ValueError(f"Unsupported database backend: {backend}")


def create_readonly_engine(database_url: str) -> Engine:
    url, connect_args = _readonly_url(database_url)
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_query_only(dbapi_conn: sqlite3.Connection, _: object) -> None:
            dbapi_conn.execute("PRAGMA query_only = ON")

    return engine


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).hex()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    return value


class QueryRunner:
    """Runs already-validated SQL with a row cap and a hard time limit."""

    def __init__(self, engine: Engine, *, timeout_ms: int, max_rows: int) -> None:
        self.engine = engine
        self.timeout_ms = timeout_ms
        self.max_rows = max_rows

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    def execute(self, sql: str) -> QueryResult:
        started = time.perf_counter()
        with self.engine.connect() as conn:
            raw = conn.connection.driver_connection
            try:
                if self.dialect == "sqlite":
                    deadline = started + self.timeout_ms / 1000
                    raw.set_progress_handler(  # type: ignore[union-attr]
                        lambda: int(time.perf_counter() > deadline), SQLITE_PROGRESS_OPS
                    )
                elif self.dialect == "postgresql":
                    conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(self.timeout_ms)}")
                result = conn.execution_options(no_parameters=True).exec_driver_sql(sql)
                columns = list(result.keys())
                fetched = result.fetchmany(self.max_rows + 1)
            except (OperationalError, DBAPIError) as exc:
                message = str(exc.orig) if exc.orig is not None else str(exc)
                if _is_timeout(message):
                    raise QueryTimeoutError(
                        f"Query exceeded the {self.timeout_ms} ms time limit"
                    ) from exc
                raise QueryExecutionError(message) from exc
            finally:
                if self.dialect == "sqlite":
                    raw.set_progress_handler(None, 0)  # type: ignore[union-attr]
                conn.rollback()

        rows = [[to_jsonable(v) for v in row] for row in fetched[: self.max_rows]]
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=len(fetched) > self.max_rows,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )


def _is_timeout(message: str) -> bool:
    lowered = message.lower()
    return (
        "interrupted" in lowered
        or "statement timeout" in lowered
        or "canceling statement" in lowered
    )
