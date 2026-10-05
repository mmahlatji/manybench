"""The universal experiment model — language-neutral."""
from __future__ import annotations

from dataclasses import dataclass, field

from manybench.core.config import MeasurementConfig, ProfilingConfig, WarmupConfig
from manybench.core.discovery import Project, Routine
from manybench.core.fixtures import Fixture
from manybench.core.parameters import Parameter


@dataclass
class Experiment:
    """The universal, language-neutral experiment model.

    This is the central abstraction of ManyBench: it owns what is being measured
    (target, parameters, fixture, warmup/measurement config) while language adapters
    own how it is translated into a concrete benchmark framework.
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
