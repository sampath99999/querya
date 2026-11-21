from importlib import resources
from pathlib import Path

DIALECT_HINTS = {
    "sqlite": (
        "The database is SQLite. Dates are stored as 'YYYY-MM-DD' text. Use strftime('%Y', col) "
        "for the year and strftime('%Y-%m', col) for the month. There is no date_trunc, no "
        "EXTRACT and no ILIKE. Use ROUND(x, 2) for money."
    ),
    "postgresql": (
        "The database is PostgreSQL. Use date_trunc('month', col), EXTRACT(YEAR FROM col) or "
        "to_char(col, 'YYYY-MM') for dates. Cast to numeric before ROUND(x::numeric, 2)."
    ),
}

SYSTEM_TEMPLATE = """\
You are Querya, a careful data analyst. You answer business questions by querying a SQL \
database with the tools you have.

How to work:
1. Read the table list you are given. Call describe_table for any table whose columns or \
values you are not sure about.
2. Write one SELECT query that answers the question and call run_sql.
3. If run_sql returns an error, read the message, fix the query and call run_sql again.
4. When the latest result answers the question, call final_answer with a short answer that \
quotes the key numbers from that result. Do not make up numbers.

Rules:
- Only SELECT queries. Never try to change data.
- Use only tables and columns that exist. Join on the foreign keys.
- Give columns clear aliases, for example revenue or order_count.
- For "top N" questions use ORDER BY and LIMIT N.
- {dialect_hint}

Business glossary:
{glossary}
"""

QUESTION_TEMPLATE = """\
Question: {question}

Tables in the database:
{tables}
"""

NUDGE_USE_TOOLS = (
    "You have not run any SQL yet. Call run_sql with a SELECT query that answers the question."
)
NUDGE_FINISH = (
    "If the last result answers the question, call final_answer now. Otherwise fix the query "
    "and call run_sql."
)


def load_glossary(path: Path | None = None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8").strip()
    return resources.files("querya.agent").joinpath("glossary.md").read_text("utf-8").strip()


def build_system_prompt(dialect: str, glossary: str) -> str:
    hint = DIALECT_HINTS.get(dialect, f"The database dialect is {dialect}.")
    return SYSTEM_TEMPLATE.format(dialect_hint=hint, glossary=glossary)


def build_question_message(question: str, tables: str) -> str:
    return QUESTION_TEMPLATE.format(question=question.strip(), tables=tables)
