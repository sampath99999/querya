import pytest

from querya.sql_guard import MAX_SQL_LENGTH, SQLGuard, UnsafeSQLError, strip_code_fences

TABLES = ["customers", "orders", "order_items", "products", "payments", "regions"]


@pytest.fixture
def guard() -> SQLGuard:
    return SQLGuard("sqlite", max_rows=200, allowed_tables=TABLES)


@pytest.fixture
def pg_guard() -> SQLGuard:
    return SQLGuard("postgresql", max_rows=200, allowed_tables=TABLES)


REJECTED_SQLITE = [
    pytest.param("", id="empty"),
    pytest.param("   \n\t ", id="whitespace"),
    pytest.param(";", id="only-semicolon"),
    pytest.param("DROP TABLE orders", id="drop"),
    pytest.param("dRoP tAbLe orders", id="drop-mixed-case"),
    pytest.param("DELETE FROM orders", id="delete"),
    pytest.param("UPDATE orders SET status = 'x'", id="update"),
    pytest.param("INSERT INTO regions VALUES (9, 'x')", id="insert"),
    pytest.param("REPLACE INTO regions VALUES (1, 'x')", id="replace"),
    pytest.param("INSERT INTO regions SELECT * FROM regions", id="insert-select"),
    pytest.param("CREATE TABLE x AS SELECT * FROM orders", id="ctas"),
    pytest.param("CREATE TEMP VIEW v AS SELECT 1", id="create-view"),
    pytest.param("ALTER TABLE orders ADD COLUMN x INTEGER", id="alter"),
    pytest.param("SELECT 1; DROP TABLE orders", id="stacked-drop"),
    pytest.param("SELECT 1; SELECT 2", id="two-selects"),
    pytest.param("SELECT 1 -- comment\n; DELETE FROM orders", id="comment-then-stacked"),
    pytest.param("BEGIN; DELETE FROM orders; COMMIT", id="transaction"),
    pytest.param("PRAGMA table_info(orders)", id="pragma"),
    pytest.param("PRAGMA writable_schema = 1", id="pragma-write"),
    pytest.param("ATTACH DATABASE 'evil.db' AS evil", id="attach"),
    pytest.param("DETACH DATABASE main", id="detach"),
    pytest.param("VACUUM", id="vacuum"),
    pytest.param("VACUUM INTO 'copy.db'", id="vacuum-into"),
    pytest.param("EXPLAIN QUERY PLAN SELECT 1", id="explain"),
    pytest.param("SELECT load_extension('evil.so')", id="load-extension"),
    pytest.param("SELECT writefile('x.txt', 'data')", id="writefile"),
    pytest.param("SELECT * FROM pragma_table_info('orders')", id="pragma-function"),
    pytest.param("SELECT sqlite_version()", id="sqlite-function"),
    pytest.param("SELECT * FROM sqlite_master", id="sqlite-master"),
    pytest.param("SELECT * FROM main.sqlite_schema", id="sqlite-schema-qualified"),
    pytest.param("SELECT * FROM temp.orders", id="temp-schema"),
    pytest.param("SELECT * FROM evil.orders", id="attached-schema"),
    pytest.param("SELECT * FROM users", id="unknown-table"),
    pytest.param(
        "SELECT * FROM orders WHERE order_id IN (SELECT rowid FROM sqlite_master)",
        id="system-table-in-subquery",
    ),
    pytest.param(
        "SELECT name FROM products UNION SELECT sql FROM sqlite_master",
        id="system-table-in-union",
    ),
    pytest.param("SELECT * FROM orders WHERE", id="syntax-error"),
    pytest.param("SELECT 'unterminated", id="unterminated-string"),
    pytest.param("SELECT\x00 1", id="nul-byte"),
    pytest.param("REINDEX orders", id="reindex"),
]


@pytest.mark.parametrize("sql", REJECTED_SQLITE)
def test_rejects_unsafe_sqlite(guard: SQLGuard, sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        guard.check(sql)


REJECTED_POSTGRES = [
    pytest.param("WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d", id="dml-in-cte"),
    pytest.param(
        "WITH u AS (UPDATE orders SET status = 'x' RETURNING *) SELECT count(*) FROM u",
        id="update-in-cte",
    ),
    pytest.param("SELECT * INTO backup FROM orders", id="select-into"),
    pytest.param("SELECT * FROM orders FOR UPDATE", id="for-update"),
    pytest.param("SELECT * FROM orders FOR SHARE", id="for-share"),
    pytest.param("SELECT pg_sleep(10)", id="pg-sleep"),
    pytest.param("SELECT pg_read_file('/etc/passwd')", id="pg-read-file"),
    pytest.param("SELECT lo_import('/etc/passwd')", id="lo-import"),
    pytest.param("SELECT query_to_xml('DELETE FROM orders', true, true, '')", id="dynamic-sql"),
    pytest.param("SELECT set_config('statement_timeout', '0', false)", id="set-config"),
    pytest.param("SELECT nextval('orders_order_id_seq')", id="nextval"),
    pytest.param("SELECT * FROM dblink('host=evil', 'SELECT 1') AS t(x int)", id="dblink"),
    pytest.param("SET statement_timeout = 0", id="set"),
    pytest.param("SET ROLE postgres", id="set-role"),
    pytest.param("RESET ALL", id="reset"),
    pytest.param("COPY orders TO '/tmp/orders.csv'", id="copy-to"),
    pytest.param("COPY orders FROM PROGRAM 'curl evil'", id="copy-program"),
    pytest.param("GRANT ALL ON orders TO public", id="grant"),
    pytest.param("TRUNCATE orders", id="truncate"),
    pytest.param("LOCK TABLE orders", id="lock"),
    pytest.param("SELECT * FROM pg_catalog.pg_user", id="pg-catalog"),
    pytest.param("SELECT * FROM pg_shadow", id="pg-shadow"),
    pytest.param("SELECT * FROM information_schema.tables", id="information-schema"),
    pytest.param("SELECT * FROM otherdb.public.orders", id="cross-database"),
    pytest.param("DO $$ BEGIN DELETE FROM orders; END $$", id="do-block"),
    pytest.param("CALL cleanup()", id="call"),
    pytest.param("PREPARE p AS DELETE FROM orders", id="prepare"),
    pytest.param("LISTEN channel", id="listen"),
]


@pytest.mark.parametrize("sql", REJECTED_POSTGRES)
def test_rejects_unsafe_postgres(pg_guard: SQLGuard, sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        pg_guard.check(sql)


def test_rejects_oversized_query(guard: SQLGuard) -> None:
    sql = "SELECT 1 " + " " * MAX_SQL_LENGTH
    with pytest.raises(UnsafeSQLError, match="longer than"):
        guard.check(sql + "+ 1")


def test_error_messages_are_useful_to_the_model(guard: SQLGuard) -> None:
    with pytest.raises(UnsafeSQLError, match="Available tables: customers"):
        guard.check("SELECT * FROM sales")
    with pytest.raises(UnsafeSQLError, match="single statement"):
        guard.check("SELECT 1; SELECT 2")
    with pytest.raises(UnsafeSQLError, match="Only SELECT"):
        guard.check("DELETE FROM orders")


def test_adds_limit_when_missing(guard: SQLGuard) -> None:
    result = guard.check("SELECT * FROM orders")
    assert result.sql.endswith("LIMIT 200")
    assert result.limit_applied
    assert result.tables == {"orders"}


def test_keeps_small_limit(guard: SQLGuard) -> None:
    result = guard.check("SELECT * FROM orders ORDER BY order_date DESC LIMIT 10")
    assert result.sql.endswith("LIMIT 10")
    assert not result.limit_applied


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders LIMIT 100000",
        "SELECT * FROM orders LIMIT -1",
        "SELECT * FROM orders LIMIT (SELECT 5)",
        "SELECT * FROM orders LIMIT 10 + 1000",
    ],
)
def test_caps_large_or_computed_limits(guard: SQLGuard, sql: str) -> None:
    result = guard.check(sql)
    assert result.limit_applied
    assert result.sql.endswith("LIMIT 200")


def test_keeps_offset_when_capping(guard: SQLGuard) -> None:
    result = guard.check("SELECT * FROM orders LIMIT 5000 OFFSET 20")
    assert "LIMIT 200" in result.sql
    assert "OFFSET 20" in result.sql


def test_postgres_limit_all_and_fetch(pg_guard: SQLGuard) -> None:
    assert pg_guard.check("SELECT * FROM orders LIMIT ALL").sql.endswith("LIMIT 200")
    kept = pg_guard.check("SELECT * FROM orders FETCH FIRST 5 ROWS ONLY")
    assert not kept.limit_applied
    capped = pg_guard.check("SELECT * FROM orders FETCH FIRST 5000 ROWS ONLY")
    assert capped.limit_applied
    assert "200" in capped.sql


def test_limit_applies_to_whole_union(guard: SQLGuard) -> None:
    result = guard.check("SELECT name FROM products UNION ALL SELECT name FROM regions")
    assert result.sql.endswith("LIMIT 200")
    assert result.tables == {"products", "regions"}


def test_parenthesised_query_is_wrapped(guard: SQLGuard) -> None:
    result = guard.check("(SELECT name FROM regions)")
    assert result.sql.startswith("SELECT * FROM (")
    assert result.sql.endswith("LIMIT 200")


def test_allows_cte_names_that_are_not_real_tables(guard: SQLGuard) -> None:
    sql = """
        WITH monthly AS (
            SELECT strftime('%Y-%m', order_date) AS month, COUNT(*) AS n
            FROM orders GROUP BY 1
        )
        SELECT month, n FROM monthly ORDER BY month
    """
    result = guard.check(sql)
    assert result.tables == {"orders"}


def test_allows_recursive_cte(guard: SQLGuard) -> None:
    sql = (
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 5) "
        "SELECT x FROM n"
    )
    assert guard.check(sql).tables == frozenset()


def test_allows_common_analytics_sql(guard: SQLGuard) -> None:
    sql = """
        SELECT p.category,
               SUM(oi.quantity * oi.unit_price * (1 - oi.discount)) AS revenue,
               RANK() OVER (ORDER BY SUM(oi.quantity * oi.unit_price) DESC) AS rnk,
               CASE WHEN COUNT(*) > 100 THEN 'big' ELSE 'small' END AS size
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status NOT IN ('cancelled', 'returned') AND o.order_date >= '2025-01-01'
        GROUP BY p.category
        HAVING SUM(oi.quantity) > 10
        ORDER BY revenue DESC
    """
    result = guard.check(sql)
    assert result.tables == {"order_items", "products", "orders"}


def test_comments_are_dropped_from_output(guard: SQLGuard) -> None:
    result = guard.check("SELECT 1 /* ; DROP TABLE orders */ AS x")
    assert "DROP" not in result.sql.upper()


def test_keywords_inside_string_literals_are_fine(guard: SQLGuard) -> None:
    result = guard.check("SELECT 'DROP TABLE orders; --' AS note FROM regions")
    assert "'DROP TABLE orders; --'" in result.sql


def test_trailing_semicolon_and_code_fences(guard: SQLGuard) -> None:
    assert guard.check("SELECT 1;").sql == "SELECT 1 LIMIT 200"
    assert guard.check("```sql\nSELECT 1\n```").sql == "SELECT 1 LIMIT 200"


def test_table_names_are_case_insensitive(guard: SQLGuard) -> None:
    assert guard.check('SELECT * FROM "Orders"').tables == {"orders"}
    assert guard.check("SELECT * FROM main.orders").tables == {"orders"}


def test_without_allowlist_any_user_table_is_allowed() -> None:
    open_guard = SQLGuard("sqlite", max_rows=50)
    assert open_guard.check("SELECT * FROM anything").tables == {"anything"}
    with pytest.raises(UnsafeSQLError):
        open_guard.check("SELECT * FROM sqlite_master")


def test_strip_code_fences() -> None:
    assert strip_code_fences("```SQL\nSELECT 1;\n```") == "SELECT 1;"
    assert strip_code_fences("SELECT 1") == "SELECT 1"
