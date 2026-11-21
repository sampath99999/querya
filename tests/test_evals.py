from pathlib import Path

import pytest
from sqlalchemy import Engine

from querya.agent import SQLAgent
from querya.config import PROJECT_ROOT
from querya.db import QueryRunner
from querya.evals import EvalCase, EvalRunner, load_cases, results_match, save_report
from querya.sql_guard import SQLGuard
from tests.fakes import ScriptedLLM, final_answer, run_sql


@pytest.mark.parametrize(
    ("gold", "pred", "ordered", "expected"),
    [
        ([[10]], [[10.0]], False, True),
        ([[6244558.8765]], [[6244558.88]], False, True),
        ([[5.768]], [[5.8]], False, False),
        ([["2024", 1.5], ["2025", 2.5]], [[2025, 2.5], [2024, 1.5]], False, True),
        ([["2024", 1.5], ["2025", 2.5]], [[2025, 2.5], [2024, 1.5]], True, False),
        ([["web", 3]], [[3, "Web "]], False, True),
        ([["Electronics"]], [["Electronics", 999.0]], False, True),
        ([["Electronics"]], [["Books", 999.0]], False, False),
        ([["a"], ["b"]], [["a"]], False, False),
        ([["a", 1]], [["a"]], False, False),
        ([], [], False, True),
        ([[None]], [[None]], False, True),
        ([["1,234.50"]], [[1234.5]], False, True),
    ],
)
def test_results_match(gold: list, pred: list, ordered: bool, expected: bool) -> None:
    assert results_match(gold, pred, ordered=ordered) is expected


def test_results_match_pairs_columns_by_rows_not_just_values() -> None:
    gold = [["a", 1], ["b", 2]]
    swapped = [["a", 2], ["b", 1]]
    assert not results_match(gold, swapped)


def test_bundled_eval_set_is_well_formed() -> None:
    cases = load_cases(PROJECT_ROOT / "evals" / "questions.yaml")
    assert 25 <= len(cases) <= 40
    guard = SQLGuard("sqlite", max_rows=200)
    for case in cases:
        guard.check(case.sql)


async def test_eval_runner_scores_cases(make_agent, engine: Engine, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    llm = ScriptedLLM(
        [
            run_sql("SELECT COUNT(*) AS n FROM regions"),
            final_answer("6 regions"),
            run_sql("SELECT COUNT(*) FROM customers WHERE 1 = 0"),
            final_answer("0"),
        ]
    )
    agent: SQLAgent = make_agent(llm)
    runner = EvalRunner(agent, QueryRunner(engine, timeout_ms=5_000, max_rows=1_000))
    cases = [
        EvalCase(id="regions", question="How many regions?", sql="SELECT COUNT(*) FROM regions"),
        EvalCase(
            id="customers", question="How many customers?", sql="SELECT COUNT(*) FROM customers"
        ),
    ]
    report = await runner.run(cases, provider="fake", model="scripted")

    assert [c.passed for c in report.cases] == [True, False]
    summary = report.summary()
    assert summary["execution_accuracy"] == 0.5
    assert summary["avg_llm_calls"] == 2
    json_path, md_path = save_report(report, tmp_path)
    assert json_path.exists()
    assert "Execution accuracy | 1/2 (50.0%)" in md_path.read_text(encoding="utf-8")
