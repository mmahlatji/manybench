"""Detect Java projects and their build system."""
from __future__ import annotations

from pathlib import Path

from polybench.core.discovery import ProjectInfo

_IGNORED_DIRS = {
    ".git", ".venv", "venv", "bin", "build", "out", "target", "node_modules", "__pycache__",
}

_BUILD_SYSTEM_MARKERS = [
    ("gradle", ("build.gradle", "build.gradle.kts")),
    ("maven", ("pom.xml",)),
    ("javac", ("Makefile",)),
]


def _java_files(path: Path) -> list[Path]:
    """Return all ``*.java`` files under ``path``, skipping build/tool directories."""
    files: list[Path] = []
    for candidate in path.rglob("*.java"):
        if any(part in _IGNORED_DIRS for part in candidate.parts):
            continue
        files.append(candidate)
    return files


def detect_build_system(path: Path) -> str | None:
    """Identify the project's build system from root-level marker files.

    Checks in priority order so that, e.g., a project with both ``pom.xml`` and a
    ``Makefile`` is reported as Maven rather than plain javac.
    """
    markers = {marker.name: marker for marker in path.iterdir()}
    for build_system, names in _BUILD_SYSTEM_MARKERS:
        if any(name in markers for name in names):
            return build_system
    return None


def detect(path: Path) -> ProjectInfo | None:
    """Detect whether ``path`` is a Java project.

    Returns ``None`` when the path is not a directory or contains no Java sources;
    otherwise returns a ``ProjectInfo`` describing the language and build system.
    """
    path = Path(path)
    if not path.is_dir():
        return None
    java_files = _java_files(path)
    if not java_files:
        return None
    return ProjectInfo(
        path=path,
        language="java",
        build_system=detect_build_system(path),
        benchmark_count=0,
    )
