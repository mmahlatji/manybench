"""Discover `@bench` routines in Java source files."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from polybench.adapters.java import java_source

_BENCH_RE = re.compile(r"^\s*//\s*@bench\s+([A-Za-z_$][\w$-]*)\s*$")
_BENCH_PARAM_RE = re.compile(r"^\s*//\s*@bench-param\s+([A-Za-z_$][\w$]*)\s*=\s*(.+?)\s*$")
_BENCH_FIXTURE_RE = re.compile(r"^\s*//\s*@bench-fixture\s+([A-Za-z_$][\w$]*)\s*$")
_COMMENT_ANNOT_RE = re.compile(r"^\s*//\s*@bench(-\w+)?\s")

_IGNORED_DIRS = {".git", "bin", "build", "out", "target"}


@dataclass
class BenchParam:
    """One ``@bench-param`` line: either a fixed value list or a generator call."""

    name: str
    values: list[str] | None = None
    generator: str | None = None
    generator_args: list[str] = field(default_factory=list)


@dataclass
class ParsedBenchmark:
    """A single ``@bench`` routine fully parsed from source."""

    benchmark_name: str
    file: Path
    line: int
    package: str
    class_name: str
    method_name: str
    is_static: bool
    return_type: str
    param_types: list[tuple[str, str]]
    params: list[BenchParam]
    fixture_ref: str | None
    java_file: java_source.JavaFile


@dataclass
class ParsedFixture:
    """A ``@bench-fixture`` factory method parsed from source."""

    name: str
    file: Path
    line: int
    package: str
    class_name: str
    method_name: str
    is_static: bool
    return_type: str
    param_types: list[tuple[str, str]]
    java_file: java_source.JavaFile


@dataclass
class ScanResult:
    """The outcome of scanning a project: benchmarks and fixture definitions."""

    benchmarks: list[ParsedBenchmark]
    fixtures: list[ParsedFixture]


def _parse_bench_param(name: str, value_expr: str) -> BenchParam:
    """Parse the right-hand side of a ``@bench-param`` into a ``BenchParam``.

    Three shapes are accepted:
      ``[1, 2, 3]``        -> a fixed list of values
      ``gen(a, b)``        -> a generator with arguments
      ``42``               -> a single value (wrapped in a one-element list)
    """
    if value_expr.startswith("[") and value_expr.endswith("]"):
        inner = value_expr[1:-1]
        values = [v.strip() for v in java_source._split_top_level(inner)]
        return BenchParam(name=name, values=values)
    gen_match = re.match(r"^([A-Za-z_$][\w$]*)\s*\((.*)\)$", value_expr)
    if gen_match:
        gen_name = gen_match.group(1)
        args = (
            [a.strip() for a in java_source._split_top_level(gen_match.group(2))]
            if gen_match.group(2).strip()
            else []
        )
        return BenchParam(name=name, generator=gen_name, generator_args=args)
    return BenchParam(name=name, values=[value_expr])


def _find_method(lines: list[str], start: int) -> tuple[java_source.MethodSig | None, int]:
    """Return the first method declaration at or after ``start`` and its 1-based line.

    Skips blank lines and comment lines. Returns ``(None, line)`` when the next
    meaningful line is not a parseable method declaration.
    """
    for idx in range(start, len(lines)):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        sig = java_source.parse_method(stripped)
        return sig, idx + 1
    return None, start + 1


def _iter_java_files(path: Path):
    """Yield ``*.java`` files under ``path`` in sorted order, skipping build dirs."""
    for java_file_path in sorted(path.rglob("*.java")):
        if any(part in _IGNORED_DIRS for part in java_file_path.parts):
            continue
        yield java_file_path


def scan(path: Path) -> ScanResult:
    """Discover all ``@bench`` benchmarks and ``@bench-fixture`` definitions in ``path``.

    Scans each Java file in a single line-by-line pass:

    - a ``@bench <name>`` line collects its following ``@bench-param`` /
      ``@bench-fixture`` comment block, then parses the method declaration below it
      into a ``ParsedBenchmark``;
    - a standalone ``@bench-fixture <name>`` line (not part of a ``@bench`` block)
      marks the method below it as a fixture *definition*.

    The single pass is important: a ``@bench-fixture`` line that appears inside a
    ``@bench`` block is a *reference*, not a definition, and is consumed there so it
    is never mistaken for a fixture factory.
    """
    path = Path(path)
    benchmarks: list[ParsedBenchmark] = []
    fixtures: list[ParsedFixture] = []

    for java_file_path in _iter_java_files(path):
        text = java_file_path.read_text(encoding="utf-8", errors="replace")
        jf = java_source.parse_file(str(java_file_path), text)
        class_name = java_file_path.stem
        lines = text.splitlines()

        i = 0
        while i < len(lines):
            bench_match = _BENCH_RE.match(lines[i])
            if bench_match:
                benchmark_name = bench_match.group(1)
                annots: list[str] = []
                j = i + 1
                # Collect contiguous @bench-* comment lines (and blank separators).
                while j < len(lines):
                    if _COMMENT_ANNOT_RE.match(lines[j]):
                        annots.append(lines[j].strip())
                        j += 1
                    elif lines[j].strip() == "":
                        j += 1
                    else:
                        break

                method_sig, method_line = _find_method(lines, j)
                if method_sig is None:
                    i = j + 1
                    continue

                params: list[BenchParam] = []
                fixture_ref: str | None = None
                for annot in annots:
                    pm = _BENCH_PARAM_RE.match(annot)
                    if pm:
                        params.append(_parse_bench_param(pm.group(1), pm.group(2)))
                        continue
                    fm = _BENCH_FIXTURE_RE.match(annot)
                    if fm:
                        fixture_ref = fm.group(1)

                benchmarks.append(
                    ParsedBenchmark(
                        benchmark_name=benchmark_name,
                        file=java_file_path,
                        line=method_line,
                        package=jf.package,
                        class_name=class_name,
                        method_name=method_sig.name,
                        is_static=method_sig.is_static,
                        return_type=method_sig.return_type,
                        param_types=method_sig.params,
                        params=params,
                        fixture_ref=fixture_ref,
                        java_file=jf,
                    )
                )
                i = j
                continue

            fixture_match = _BENCH_FIXTURE_RE.match(lines[i])
            if fixture_match:
                method_sig, method_line = _find_method(lines, i + 1)
                if method_sig is not None:
                    fixtures.append(
                        ParsedFixture(
                            name=fixture_match.group(1),
                            file=java_file_path,
                            line=method_line,
                            package=jf.package,
                            class_name=class_name,
                            method_name=method_sig.name,
                            is_static=method_sig.is_static,
                            return_type=method_sig.return_type,
                            param_types=method_sig.params,
                            java_file=jf,
                        )
                    )
                    i = method_line
                else:
                    i += 1
                continue

            i += 1

    return ScanResult(benchmarks=benchmarks, fixtures=fixtures)
