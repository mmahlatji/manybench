"""Normalize raw JMH JSON into the universal BenchmarkResult model."""
from __future__ import annotations

from manybench.core.results import BenchmarkResult, TimingResult

_UNIT_TO_NS = {
    "ns/op": 1.0,
    "us/op": 1e3,
    "ms/op": 1e6,
    "s/op": 1e9,
}


def _coerce(value):
    """Convert a JMH @Param string value into a Python bool/int/float (or string).

    JMH reports all parameter values as strings, so the parser re-infers their types.
    """
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if value.lstrip("+-").isdigit():
            return int(value)
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _to_ns(value, factor: float) -> int | None:
    """Scale a JMH metric value into integer nanoseconds using the unit factor."""
    if value is None:
        return None
    return int(round(float(value) * factor))


def parse(raw_json: list | None, experiment_id: str) -> list[BenchmarkResult]:
    """Normalize raw JMH JSON (a list of result objects) into BenchmarkResults.

    For each entry it maps primaryMetric onto a TimingResult: median and p95 come
    from scorePercentiles, the mean from score, all converted to nanoseconds.
    Parameter values (entry["params"]) are type-coerced.
    """
    if not raw_json:
        return []
    results: list[BenchmarkResult] = []
    for entry in raw_json:
        primary = entry.get("primaryMetric") or {}
        factor = _UNIT_TO_NS.get(primary.get("scoreUnit", "ns/op"), 1.0)
        percentiles = primary.get("scorePercentiles") or {}

        timing = TimingResult(
            median_ns=_to_ns(percentiles.get("50.0"), factor),
            mean_ns=_to_ns(primary.get("score"), factor),
            p95_ns=_to_ns(percentiles.get("95.0"), factor),
        )
        params = {k: _coerce(v) for k, v in (entry.get("params") or {}).items()}
        results.append(
            BenchmarkResult(
                experiment_id=experiment_id,
                benchmark_name=entry.get("benchmark", experiment_id),
                parameters=params,
                timing=timing,
            )
        )
    return results
