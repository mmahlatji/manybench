"""Project and routine discovery model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Project:
    """A discovered project: its location, language, and build system."""

    path: Path
    language: str
    build_system: str | None = None


@dataclass
class ProjectInfo:
    """Language-adapter detection result for a project."""

    path: Path
    language: str
    build_system: str | None = None
    benchmark_count: int = 0


@dataclass
class Routine:
    """A single benchmarkable routine discovered in source (via ``@bench``)."""

    name: str
    benchmark_name: str
    file: Path
    language: str
    symbol: str
    line: int
    parameters: list[str]
