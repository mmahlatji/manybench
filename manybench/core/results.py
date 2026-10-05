"""Normalized result model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimingResult:
    """Normalized timing statistics, all in integer nanoseconds."""

    median_ns: int | None = None
    mean_ns: int | None = None
    p95_ns: int | None = None


@dataclass
class MemoryResult:
    """Normalized memory statistics (populated only when a profiler provides them)."""

    peak_bytes: int | None = None


@dataclass
class Environment:
    """The machine/git context a run was captured in."""

    machine: str | None = None
    commit_hash: str | None = None
    branch: str | None = None


@dataclass
class Artifact:
    """A sidecar file produced by a run (e.g. a profiling report)."""

    type: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """The universal result record consumed by the UI and comparison engine."""

    experiment_id: str
    benchmark_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timing: TimingResult | None = None
    memory: MemoryResult | None = None
    counters: dict[str, float] = field(default_factory=dict)
    environment: Environment | None = None
    artifacts: list[Artifact] = field(default_factory=list)
