from querya.agent import Toolbox


def test_list_tables_shows_columns_and_counts(toolbox: Toolbox) -> None:
    outcome = toolbox.list_tables()
    assert not outcome.is_error
    assert "- orders (" in outcome.content
    assert "order_id, customer_id, order_date" in outcome.content
    assert outcome.detail is not None
    assert len(outcome.detail["tables"]) == 6


def test_describe_table_includes_keys_and_samples(toolbox: Toolbox) -> None:
    outcome = toolbox.describe_table("order_items")
    assert "order_id INTEGER" in outcome.content
    assert "order_item_id INTEGER PRIMARY KEY" in outcome.content
    assert "product_id -> products(product_id)" in outcome.content
    assert "Sample rows:" in outcome.content


async def test_describe_unknown_table_is_an_error(toolbox: Toolbox) -> None:
    outcome = await toolbox.call("describe_table", {"table": "sales"})
    assert outcome.is_error
    assert "Available tables" in outcome.content


async def test_run_sql_returns_preview_and_full_result(toolbox: Toolbox) -> None:
    outcome = await toolbox.call("run_sql", {"sql": "SELECT order_id FROM orders ORDER BY 1"})
    assert not outcome.is_error
    assert outcome.result is not None
    assert outcome.result.row_count == 50
    assert outcome.result.truncated
    assert outcome.sql is not None
    assert outcome.sql.endswith("LIMIT 50")
    assert "showing first 10" in outcome.content
    assert outcome.content.count("\n") == 11


async def test_run_sql_rejects_writes_before_touching_the_db(toolbox: Toolbox) -> None:
    outcome = await toolbox.call("run_sql", {"sql": "DELETE FROM orders"})
    assert outcome.is_error
    assert outcome.content.startswith("Rejected by the SQL guard")
    assert outcome.result is None


async def test_run_sql_reports_database_errors(toolbox: Toolbox) -> None:
    outcome = await toolbox.call("run_sql", {"sql": "SELECT total FROM orders"})
    assert outcome.is_error
    assert "no such column: total" in outcome.content


async def test_run_sql_accepts_query_alias_and_fences(toolbox: Toolbox) -> None:
    outcome = await toolbox.call(
        "run_sql", {"query": "```sql\nSELECT COUNT(*) AS n FROM regions\n```"}
    )
    assert not outcome.is_error
    assert outcome.result is not None
    assert outcome.result.rows == [[6]]


async def test_bad_arguments_and_unknown_tools(toolbox: Toolbox) -> None:
    missing = await toolbox.call("run_sql", {})
    assert missing.is_error
    unparsed = await toolbox.call("run_sql", {"_unparsed": "{sql: oops"})
    assert unparsed.is_error
    assert "JSON" in unparsed.content
    unknown = await toolbox.call("drop_everything", {})
    assert unknown.is_error
    assert "run_sql" in unknown.content
