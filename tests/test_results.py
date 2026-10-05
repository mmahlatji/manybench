import json

from manybench.core.results import BenchmarkResult, TimingResult


def test_benchmark_result_defaults() -> None:
    result = BenchmarkResult(experiment_id="e1", benchmark_name="physics-step")
    assert result.parameters == {}
    assert result.counters == {}
    assert result.artifacts == []


def test_timing_result_roundtrip() -> None:
    result = BenchmarkResult(
        experiment_id="e1",
        benchmark_name="physics-step",
        parameters={"particles": 100000},
        timing=TimingResult(median_ns=12840000, mean_ns=12910000, p95_ns=13210000),
    )
    payload = json.loads(json.dumps(result.__dict__, default=str))
    assert payload["benchmark_name"] == "physics-step"
    assert payload["parameters"]["particles"] == 100000
