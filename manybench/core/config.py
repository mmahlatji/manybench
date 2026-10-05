"""Warmup, measurement, and profiling configuration."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WarmupConfig:
    """How the benchmark engine should warm up before timed measurement."""

    iterations: int = 5
    time_ms: int | None = None

    def __post_init__(self) -> None:
        # Warmup may legitimately be zero (skip warmup), but never negative.
        if self.iterations < 0:
            raise ValueError("warmup iterations must be >= 0")


@dataclass
class MeasurementConfig:
    """How many timed iterations to collect for the benchmark."""

    iterations: int = 20
    time_ms: int | None = None

    def __post_init__(self) -> None:
        # At least one measurement iteration is required to produce a score.
        if self.iterations < 1:
            raise ValueError("measurement iterations must be >= 1")


@dataclass
class ProfilingConfig:
    """Optional profiling configuration (Phase 3 — not yet wired up)."""

    profiler: str | None = None
    events: list[str] = field(default_factory=list)
