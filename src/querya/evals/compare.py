"""Execution-accuracy matching: compare result values, not SQL text or column names.

A prediction matches when it has the same number of rows and every reference column can be
paired with a distinct predicted column so that the projected rows are equal. Extra predicted
columns are allowed, so "category, revenue" still matches a reference that only returns the
category. Numbers are compared with a small tolerance; strings ignore case and padding.
"""

import math
from collections.abc import Sequence
from itertools import permutations
from typing import Any

Value = float | str | None
REL_TOL = 1e-4
ABS_TOL = 0.01
MAX_EXTRA_COLUMNS = 6


def normalize(value: Any) -> Value:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return text.lower()
    return number if math.isfinite(number) else text.lower()


def values_equal(a: Value, b: Value) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    return a == b


def _sort_key(value: Value) -> tuple[int, float, str]:
    if value is None:
        return (0, 0.0, "")
    if isinstance(value, float):
        return (1, round(value, 2), "")
    return (2, 0.0, value)


def _rows_equal(a: Sequence[Sequence[Value]], b: Sequence[Sequence[Value]]) -> bool:
    return all(
        len(ra) == len(rb) and all(values_equal(x, y) for x, y in zip(ra, rb, strict=True))
        for ra, rb in zip(a, b, strict=True)
    )


def _sorted_rows(rows: Sequence[Sequence[Value]]) -> list[tuple[Value, ...]]:
    return sorted((tuple(r) for r in rows), key=lambda r: tuple(_sort_key(v) for v in r))


def _column(rows: Sequence[Sequence[Value]], index: int) -> list[Value]:
    return [row[index] for row in rows]


def _column_compatible(gold: list[Value], pred: list[Value], ordered: bool) -> bool:
    if not ordered:
        gold, pred = sorted(gold, key=_sort_key), sorted(pred, key=_sort_key)
    return all(values_equal(g, p) for g, p in zip(gold, pred, strict=True))


def results_match(
    gold_rows: Sequence[Sequence[Any]],
    pred_rows: Sequence[Sequence[Any]],
    *,
    ordered: bool = False,
) -> bool:
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    gold = [[normalize(v) for v in row] for row in gold_rows]
    pred = [[normalize(v) for v in row] for row in pred_rows]
    n_gold, n_pred = len(gold[0]), len(pred[0])
    if n_pred < n_gold or n_pred - n_gold > MAX_EXTRA_COLUMNS:
        return False

    candidates = [
        [
            j
            for j in range(n_pred)
            if _column_compatible(_column(gold, i), _column(pred, j), ordered)
        ]
        for i in range(n_gold)
    ]
    if any(not c for c in candidates):
        return False

    gold_sorted = gold if ordered else _sorted_rows(gold)
    for mapping in permutations(range(n_pred), n_gold):
        if any(mapping[i] not in candidates[i] for i in range(n_gold)):
            continue
        projected = [[row[j] for j in mapping] for row in pred]
        if not ordered:
            projected = [list(r) for r in _sorted_rows(projected)]
        if _rows_equal(gold_sorted, projected):
            return True
    return False
