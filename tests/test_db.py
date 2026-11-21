from pathlib import Path

import pytest
from sqlalchemy import Engine

from querya.db import (
    DatabaseNotFoundError,
    QueryExecutionError,
    QueryRunner,
    QueryTimeoutError,
    SchemaCatalog,
    UnknownTableError,
    create_readonly_engine,
)


def test_connection_is_read_only_even_without_the_guard(engine: Engine) -> None:
    runner = QueryRunner(engine, timeout_ms=2_000, max_rows=10)
    for statement in (
        "DELETE FROM orders",
        "UPDATE regions SET name = 'x'",
        "CREATE TABLE evil (x INTEGER)",
        "DROP TABLE regions",
    ):
        with pytest.raises(QueryExecutionError, match="readonly"):
            runner.execute(statement)
    assert runner.execute("SELECT COUNT(*) FROM regions").rows == [[6]]


def test_runaway_query_hits_the_time_limit(engine: Engine) -> None:
    runner = QueryRunner(engine, timeout_ms=200, max_rows=10)
    endless = (
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    )
    with pytest.raises(QueryTimeoutError, match="200 ms"):
        runner.execute(endless)
    assert runner.execute("SELECT 1").rows == [[1]]


def test_rows_are_capped_and_marked_truncated(engine: Engine) -> None:
    runner = QueryRunner(engine, timeout_ms=2_000, max_rows=5)
    result = runner.execute("SELECT order_id, order_date, shipping_cost FROM orders")
    assert result.row_count == 5
    assert result.truncated
    assert result.columns == ["order_id", "order_date", "shipping_cost"]
    assert isinstance(result.rows[0][1], str)


def test_execution_error_carries_the_database_message(engine: Engine) -> None:
    runner = QueryRunner(engine, timeout_ms=2_000, max_rows=5)
    with pytest.raises(QueryExecutionError, match="no such column: revenue"):
        runner.execute("SELECT revenue FROM orders")


def test_percent_signs_are_not_treated_as_parameters(engine: Engine) -> None:
    runner = QueryRunner(engine, timeout_ms=2_000, max_rows=5)
    result = runner.execute("SELECT strftime('%Y', order_date) AS y, '10:30' AS t FROM orders")
    assert result.rows[0][0] in ("2024", "2025")
    assert result.rows[0][1] == "10:30"


def test_missing_sqlite_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(DatabaseNotFoundError, match="querya seed"):
        create_readonly_engine(f"sqlite:///{(tmp_path / 'nope.db').as_posix()}")


def test_in_memory_sqlite_is_rejected() -> None:
    with pytest.raises(ValueError, match="file-backed"):
        create_readonly_engine("sqlite://")


def test_catalog_describes_tables(catalog: SchemaCatalog) -> None:
    assert catalog.table_names == [
        "customers",
        "order_items",
        "orders",
        "payments",
        "products",
        "regions",
    ]
    orders = catalog.describe("ORDERS")
    assert orders.row_count > 0
    assert {c.name for c in orders.columns} >= {"order_id", "order_date", "status"}
    assert orders.foreign_keys[0].references_table == "customers"
    assert len(orders.sample_rows) == 3
    with pytest.raises(UnknownTableError, match="Available tables"):
        catalog.describe("sales")
