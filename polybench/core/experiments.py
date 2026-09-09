"""The universal experiment model — language-neutral."""
from __future__ import annotations

from dataclasses import dataclass, field

from polybench.core.config import MeasurementConfig, ProfilingConfig, WarmupConfig
from polybench.core.discovery import Project, Routine
from polybench.core.fixtures import Fixture
from polybench.core.parameters import Parameter


@dataclass
class Experiment:
    """The universal, language-neutral experiment model.

    This is the central abstraction of PolyBench: it owns *what* is being measured
    (target, parameters, fixture, warmup/measurement config) while language adapters
    own *how* it is translated into a concrete benchmark framework.
    """

    id: str
    name: str
    project: Project
    target: Routine
    fixture: Fixture | None = None
    parameters: list[Parameter] = field(default_factory=list)
    warmup: WarmupConfig = field(default_factory=WarmupConfig)
    measurement: MeasurementConfig = field(default_factory=MeasurementConfig)
    profiling: ProfilingConfig | None = None
