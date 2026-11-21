import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel

from querya.db import (
    QueryExecutionError,
    QueryResult,
    QueryRunner,
    QueryTimeoutError,
    SchemaCatalog,
    UnknownTableError,
)
from querya.llm import ToolSpec
from querya.sql_guard import SQLGuard, UnsafeSQLError

logger = logging.getLogger(__name__)

LIST_TABLES = "list_tables"
DESCRIBE_TABLE = "describe_table"
RUN_SQL = "run_sql"
FINAL_ANSWER = "final_answer"

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name=LIST_TABLES,
        description="List every table with its row count and column names.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    ToolSpec(
        name=DESCRIBE_TABLE,
        description=(
            "Show the columns, types, keys and a few sample rows of one table. Use it before "
            "writing SQL against a table you have not seen yet."
        ),
        parameters={
            "type": "object",
            "properties": {"table": {"type": "string", "description": "Table name"}},
            "required": ["table"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name=RUN_SQL,
        description=(
            "Run one read-only SELECT query and get the result rows back. Errors are returned "
            "as text so you can fix the query and try again."
        ),
        parameters={
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "A single SELECT query"}},
            "required": ["sql"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name=FINAL_ANSWER,
        description=(
            "Finish with the answer for the user. Call this once the last run_sql result "
            "answers the question. State the key numbers from that result."
        ),
        parameters={
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "One to three plain sentences"}
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    ),
]


class ToolOutcome(BaseModel):
    content: str
    is_error: bool = False
    sql: str | None = None
    result: QueryResult | None = None
    detail: dict[str, Any] | None = None


class Toolbox:
    def __init__(
        self,
        catalog: SchemaCatalog,
        runner: QueryRunner,
        guard: SQLGuard,
        *,
        preview_rows: int = 25,
    ) -> None:
        self.catalog = catalog
        self.runner = runner
        self.guard = guard
        self.preview_rows = preview_rows

    @property
    def dialect(self) -> str:
        return self.runner.dialect

    def list_tables(self) -> ToolOutcome:
        summaries = self.catalog.summaries()
        lines = [f"- {t.name} ({t.row_count} rows): {', '.join(t.columns)}" for t in summaries]
        return ToolOutcome(
            content="\n".join(lines),
            detail={"tables": [t.model_dump() for t in summaries]},
        )

    def describe_table(self, table: str) -> ToolOutcome:
        try:
            info = self.catalog.describe(table)
        except UnknownTableError as exc:
            return ToolOutcome(content=str(exc), is_error=True)
        cols = []
        for c in info.columns:
            flags = " PRIMARY KEY" if c.primary_key else ""
            cols.append(f"  {c.name} {c.type}{flags}")
        fks = [
            f"  {', '.join(fk.columns)} -> {fk.references_table}"
            f"({', '.join(fk.references_columns)})"
            for fk in info.foreign_keys
        ]
        parts = [f"Table {info.name} ({info.row_count} rows)", "Columns:", *cols]
        if fks:
            parts += ["Foreign keys:", *fks]
        parts += ["Sample rows:", *(json.dumps(r, default=str) for r in info.sample_rows)]
        return ToolOutcome(content="\n".join(parts), detail=info.model_dump())

    async def run_sql(self, sql: str) -> ToolOutcome:
        try:
            guarded = self.guard.check(sql)
        except UnsafeSQLError as exc:
            return ToolOutcome(content=f"Rejected by the SQL guard: {exc}", is_error=True, sql=sql)
        try:
            result = await asyncio.to_thread(self.runner.execute, guarded.sql)
        except QueryTimeoutError as exc:
            return ToolOutcome(
                content=f"{exc}. Simplify the query.", is_error=True, sql=guarded.sql
            )
        except QueryExecutionError as exc:
            return ToolOutcome(content=f"Database error: {exc}", is_error=True, sql=guarded.sql)
        if guarded.limit_applied and result.row_count >= self.guard.max_rows:
            result.truncated = True
        return ToolOutcome(content=self._format_result(result), sql=guarded.sql, result=result)

    def _format_result(self, result: QueryResult) -> str:
        shown = result.rows[: self.preview_rows]
        header = f"{result.row_count} row(s)"
        if result.truncated:
            header += f" (limited to {result.row_count} rows, more may exist)"
        if len(shown) < result.row_count:
            header += f", showing first {len(shown)}"
        lines = [header, "columns: " + json.dumps(result.columns)]
        lines += [json.dumps(row, default=str) for row in shown]
        return "\n".join(lines)

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        if "_unparsed" in arguments:
            return ToolOutcome(
                content=f"Could not parse the arguments as JSON: {arguments['_unparsed']!r}",
                is_error=True,
            )
        if name == LIST_TABLES:
            return self.list_tables()
        if name == DESCRIBE_TABLE:
            table = arguments.get("table") or arguments.get("table_name")
            if not isinstance(table, str) or not table:
                return ToolOutcome(content="describe_table needs a 'table' argument", is_error=True)
            return self.describe_table(table)
        if name == RUN_SQL:
            sql = arguments.get("sql") or arguments.get("query")
            if not isinstance(sql, str) or not sql.strip():
                return ToolOutcome(content="run_sql needs a 'sql' argument", is_error=True)
            return await self.run_sql(sql)
        known = ", ".join(t.name for t in TOOL_SPECS)
        return ToolOutcome(content=f"Unknown tool {name!r}. Available: {known}", is_error=True)
