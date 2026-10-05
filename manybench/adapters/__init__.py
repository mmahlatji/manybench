"""Language adapters translate the universal experiment model into native frameworks."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from manybench.core.discovery import ProjectInfo, Routine
from manybench.core.experiments import Experiment
from manybench.core.results import BenchmarkResult


class LanguageAdapter(ABC):
    """Translates the universal experiment model into one language's benchmark framework.

    Concrete adapters (e.g. JavaAdapter -> JMH) implement all six methods.
    Any is used as a placeholder because each adapter deals in its own
    language-specific artifact/result types.
    """

    language: str = ""

    @abstractmethod
    def detect(self, project: Any) -> ProjectInfo:
        """Return ProjectInfo if project is in this language, else None."""
        ...

    @abstractmethod
    def discover_routines(self, project: Any) -> list[Routine]:
        """Find benchmarkable routines (via @bench comments) in project."""
        ...

    @abstractmethod
    def generate_benchmark(self, experiment: Experiment) -> Any:
        """Produce a framework-specific benchmark artifact from an Experiment."""
        ...

    @abstractmethod
    def build(self, artifact: Any) -> Any:
        """Compile/assemble the benchmark artifact into something runnable."""
        ...

    @abstractmethod
    def run(self, benchmark: Any) -> Any:
        """Execute the built benchmark and capture raw output."""
        ...

    @abstractmethod
    def normalize(self, raw: Any) -> BenchmarkResult:
        """Convert raw framework output into the universal BenchmarkResult."""
        ...
