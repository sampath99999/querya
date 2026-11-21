import json
import logging
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from querya.agent import SQLAgent
from querya.db import QueryRunner
from querya.evals.compare import results_match

logger = logging.getLogger(__name__)


class EvalCase(BaseModel):
    id: str
    question: str
    sql: str
    ordered: bool = False


class CaseResult(BaseModel):
    id: str
    question: str
    passed: bool
    status: str
    answer: str | None
    sql: str | None
    error: str | None
    expected_rows: int
    actual_rows: int
    llm_calls: int
    sql_attempts: int
    steps: int
    latency_ms: float
    input_tokens: int
    output_tokens: int


class EvalReport(BaseModel):
    model: str
    provider: str
    dialect: str
    started_at: datetime
    cases: list[CaseResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    def summary(self) -> dict[str, Any]:
        if not self.cases:
            return {"total": 0}
        latencies = [c.latency_ms for c in self.cases]
        passed = sum(c.passed for c in self.cases)
        answered = sum(c.status == "succeeded" for c in self.cases)
        return {
            "total": self.total,
            "passed": passed,
            "execution_accuracy": round(passed / self.total, 4),
            "answered_rate": round(answered / self.total, 4),
            "avg_llm_calls": round(statistics.mean(c.llm_calls for c in self.cases), 2),
            "avg_sql_attempts": round(statistics.mean(c.sql_attempts for c in self.cases), 2),
            "avg_steps": round(statistics.mean(c.steps for c in self.cases), 2),
            "avg_latency_s": round(statistics.mean(latencies) / 1000, 2),
            "p50_latency_s": round(statistics.median(latencies) / 1000, 2),
            "max_latency_s": round(max(latencies) / 1000, 2),
            "total_input_tokens": sum(c.input_tokens for c in self.cases),
            "total_output_tokens": sum(c.output_tokens for c in self.cases),
        }

    def to_markdown(self) -> str:
        s = self.summary()
        lines = [
            f"# Eval run: {self.provider}/{self.model} on {self.dialect}",
            "",
            f"Started {self.started_at:%Y-%m-%d %H:%M} UTC.",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Questions | {s['total']} |",
            f"| Execution accuracy | {s['passed']}/{s['total']} ({s['execution_accuracy']:.1%}) |",
            f"| Runs that produced an answer | {s['answered_rate']:.1%} |",
            f"| Avg model calls per question | {s['avg_llm_calls']} |",
            f"| Avg SQL attempts per question | {s['avg_sql_attempts']} |",
            f"| Avg trace steps per question | {s['avg_steps']} |",
            f"| Avg / median latency | {s['avg_latency_s']} s / {s['p50_latency_s']} s |",
            f"| Tokens (in / out) | {s['total_input_tokens']} / {s['total_output_tokens']} |",
            "",
            "| Case | Pass | Calls | SQL tries | Latency (s) | Note |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for c in self.cases:
            note = (c.error or "").replace("|", "/")[:80]
            if not note and not c.passed:
                note = (
                    "values differ"
                    if c.actual_rows == c.expected_rows
                    else f"{c.actual_rows} rows, expected {c.expected_rows}"
                )
            lines.append(
                f"| {c.id} | {'yes' if c.passed else 'no'} | {c.llm_calls} | {c.sql_attempts} "
                f"| {c.latency_ms / 1000:.1f} | {note} |"
            )
        return "\n".join(lines) + "\n"


def load_cases(path: Path) -> list[EvalCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [EvalCase.model_validate(item) for item in raw]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids in eval set")
    return cases


class EvalRunner:
    def __init__(self, agent: SQLAgent, reference_runner: QueryRunner) -> None:
        self.agent = agent
        self.reference = reference_runner

    async def run_case(self, case: EvalCase) -> CaseResult:
        expected = self.reference.execute(case.sql)
        started = time.perf_counter()
        result = await self.agent.run(case.question)
        latency = (time.perf_counter() - started) * 1000
        passed = result.status == "succeeded" and results_match(
            expected.rows, result.rows, ordered=case.ordered
        )
        return CaseResult(
            id=case.id,
            question=case.question,
            passed=passed,
            status=result.status,
            answer=result.answer,
            sql=result.sql,
            error=result.error,
            expected_rows=expected.row_count,
            actual_rows=result.row_count,
            llm_calls=result.llm_calls,
            sql_attempts=result.sql_attempts,
            steps=len(result.steps),
            latency_ms=round(latency, 1),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    async def run(self, cases: list[EvalCase], *, provider: str, model: str) -> EvalReport:
        report = EvalReport(
            model=model,
            provider=provider,
            dialect=self.reference.dialect,
            started_at=datetime.now(UTC),
        )
        for i, case in enumerate(cases, start=1):
            outcome = await self.run_case(case)
            report.cases.append(outcome)
            logger.info(
                "[%d/%d] %-28s %s  %.1fs  calls=%d",
                i,
                len(cases),
                case.id,
                "PASS" if outcome.passed else "FAIL",
                outcome.latency_ms / 1000,
                outcome.llm_calls,
            )
        return report


def save_report(report: EvalReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9.-]+", "-", f"{report.provider}-{report.model}").strip("-")
    stem = f"{report.started_at:%Y%m%d-%H%M}-{slug}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = {"summary": report.summary(), **report.model_dump(mode="json")}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    return json_path, md_path
