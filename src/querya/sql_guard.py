"""Static checks that every model-written query must pass before it reaches the database.

The guard is one layer of three: it parses the SQL and only lets a single read-only query
through, the connection itself is read-only, and the runner enforces a time limit.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, ParseError, TokenError

MAX_SQL_LENGTH = 20_000

_FORBIDDEN_NODE_NAMES = (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "TruncateTable",
    "Command", "Pragma", "Attach", "Detach", "Set", "Transaction", "Commit", "Rollback",
    "Into", "Lock", "Copy", "LoadData", "Grant", "Revoke", "Use", "Analyze", "Kill",
    "Describe", "Show", "Refresh", "Cache", "Uncache", "Comment", "Declare", "Execute",
)  # fmt: skip
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = tuple(
    getattr(exp, name) for name in _FORBIDDEN_NODE_NAMES if hasattr(exp, name)
)

DENIED_FUNCTIONS = frozenset(
    {
        # SQLite
        "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
        # PostgreSQL: file access, sleeping, sessions, dynamic SQL
        "set_config", "current_setting", "nextval", "setval", "txid_current",
        "query_to_xml", "query_to_xml_and_xmlschema", "query_to_xmlschema",
        "table_to_xml", "cursor_to_xml", "database_to_xml", "schema_to_xml",
        # MySQL style
        "sleep", "benchmark", "load_file",
    }
)  # fmt: skip
DENIED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "pragma_", "sqlite_")
SYSTEM_TABLE_PREFIXES = ("sqlite_", "pg_")
ALLOWED_SCHEMAS = frozenset({"main", "public"})

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class UnsafeSQLError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GuardedSQL:
    sql: str
    pretty: str
    tables: frozenset[str]
    limit_applied: bool


def strip_code_fences(sql: str) -> str:
    return _FENCE_RE.sub("", sql.strip()).strip()


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return node.sql_name().lower()


class SQLGuard:
    def __init__(
        self,
        dialect: str,
        *,
        max_rows: int,
        allowed_tables: Iterable[str] | None = None,
    ) -> None:
        self.dialect = "postgres" if dialect == "postgresql" else dialect
        self.max_rows = max_rows
        self.allowed_tables = (
            frozenset(t.lower() for t in allowed_tables) if allowed_tables is not None else None
        )

    def check(self, sql: str) -> GuardedSQL:
        sql = strip_code_fences(sql or "")
        if not sql:
            raise UnsafeSQLError("Empty query")
        if len(sql) > MAX_SQL_LENGTH:
            raise UnsafeSQLError(f"Query is longer than {MAX_SQL_LENGTH} characters")
        if "\x00" in sql:
            raise UnsafeSQLError("Query contains a NUL byte")

        root = self._parse_single(sql)
        if not isinstance(root, exp.Query):
            raise UnsafeSQLError(
                f"Only SELECT queries are allowed, got {type(root).__name__.upper()}"
            )

        for node in root.walk():
            if isinstance(node, FORBIDDEN_NODES):
                raise UnsafeSQLError(f"{type(node).__name__.upper()} is not allowed in a query")
            if isinstance(node, exp.Func):
                self._check_function(node)

        tables = self._check_tables(root)
        query, limit_applied = self._enforce_limit(root)
        return GuardedSQL(
            sql=query.sql(dialect=self.dialect, comments=False),
            pretty=query.sql(dialect=self.dialect, comments=False, pretty=True),
            tables=tables,
            limit_applied=limit_applied,
        )

    def _parse_single(self, sql: str) -> exp.Expr:
        try:
            statements = sqlglot.parse(sql, read=self.dialect, error_level=ErrorLevel.RAISE)
        except (ParseError, TokenError) as exc:
            raise UnsafeSQLError(f"Could not parse SQL: {_first_line(exc)}") from exc
        parsed = [s for s in statements if s is not None]
        if not parsed:
            raise UnsafeSQLError("Empty query")
        if len(parsed) > 1:
            raise UnsafeSQLError("Only a single statement is allowed")
        return parsed[0]

    def _check_function(self, node: exp.Func) -> None:
        # sqlglot normalises known functions (sqlite_version -> CURRENT_VERSION), so check
        # both the canonical name and the name as it will be sent to the database.
        rendered = node.sql(dialect=self.dialect).split("(", 1)[0].strip().lower()
        for name in (_function_name(node), rendered):
            if name in DENIED_FUNCTIONS or name.startswith(DENIED_FUNCTION_PREFIXES):
                raise UnsafeSQLError(f"Function {name}() is not allowed")

    def _check_tables(self, root: exp.Expr) -> frozenset[str]:
        cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
        seen: set[str] = set()
        for table in root.find_all(exp.Table):
            if not isinstance(table.this, exp.Identifier):
                continue  # table-valued function, already vetted by the function checks
            name = table.name.lower()
            if table.catalog:
                raise UnsafeSQLError(f"Cross-database reference {table.sql()} is not allowed")
            if table.db and table.db.lower() not in ALLOWED_SCHEMAS:
                raise UnsafeSQLError(f"Schema {table.db!r} is not allowed")
            if name in cte_names and not table.db:
                continue
            if name.startswith(SYSTEM_TABLE_PREFIXES) or name == "information_schema":
                raise UnsafeSQLError(f"System table {name!r} is not allowed")
            if self.allowed_tables is not None and name not in self.allowed_tables:
                allowed = ", ".join(sorted(self.allowed_tables))
                raise UnsafeSQLError(f"Unknown table {name!r}. Available tables: {allowed}")
            seen.add(name)
        return frozenset(seen)

    def _enforce_limit(self, root: exp.Query) -> tuple[exp.Query, bool]:
        if not isinstance(root, exp.Select | exp.SetOperation):
            root = exp.select("*").from_(root.subquery("_q"))

        current = root.args.get("limit")
        value: exp.Expression | None = None
        if isinstance(current, exp.Limit):
            value = current.expression
        elif isinstance(current, exp.Fetch):
            options = current.args.get("limit_options")
            if options is None or not (
                options.args.get("percent") or options.args.get("with_ties")
            ):
                value = current.args.get("count")
        if isinstance(value, exp.Literal) and value.is_int and int(value.name) <= self.max_rows:
            return root, False
        return root.limit(self.max_rows, copy=False), True


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:300]
