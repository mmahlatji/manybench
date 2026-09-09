"""The `bench` command-line interface."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from polybench.adapters.java import JavaAdapter
from polybench.core.discovery import Project

app = typer.Typer(
    name="bench",
    help="PolyBench — local-first benchmarking across languages.",
    no_args_is_help=True,
)


def _to_serializable(value: Any) -> Any:
    """Recursively convert dataclasses/lists/dicts into plain JSON-safe structures."""
    if is_dataclass(value):
        return {k: _to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_to_serializable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_serializable(v) for k, v in value.items()}
    return value


def _emit(payload: Any, fmt: str) -> None:
    """Print ``payload`` as indented JSON or as plain text."""
    if fmt == "json":
        typer.echo(json.dumps(_to_serializable(payload), indent=2))
    elif fmt == "text":
        typer.echo(payload)
    else:
        raise typer.BadParameter(f"unknown format: {fmt!r} (expected 'text' or 'json')")


def _check_format(fmt: str) -> None:
    """Validate ``--format`` up front so an invalid value never triggers real work."""
    if fmt not in {"text", "json"}:
        raise typer.BadParameter(f"unknown format: {fmt!r} (expected 'text' or 'json')")


def _detect_java_project(cwd: Path) -> Project | None:
    """Detect a Java project in ``cwd`` and wrap it in a core ``Project``."""
    info = JavaAdapter().detect(cwd)
    if info is None:
        return None
    return Project(path=cwd, language="java", build_system=info.build_system)


@app.command("list")
def list_benchmarks(
    fmt: Annotated[str, typer.Option("--format", help="Output format: text or json")] = "text",
) -> None:
    """Discover and list benchmarks in the current project."""
    _check_format(fmt)
    cwd = Path.cwd()
    project = _detect_java_project(cwd)
    if project is None:
        _emit("No Java project detected in the current directory.", fmt)
        raise typer.Exit(code=1)

    routines = JavaAdapter().discover_routines(cwd)
    if not routines:
        _emit("No benchmarks found (add `// @bench <name>` comments).", fmt)
        raise typer.Exit(code=1)

    if fmt == "json":
        _emit({"benchmarks": [r.benchmark_name for r in routines]}, fmt)
    else:
        _emit("\n".join(r.benchmark_name for r in routines), fmt)


@app.command("run")
def run_benchmark(
    name: Annotated[str, typer.Argument(help="Benchmark name to run")],
    fmt: Annotated[str, typer.Option("--format", help="Output format: text or json")] = "text",
    forks: Annotated[int, typer.Option(help="JMH forks")] = 1,
    warmup_iterations: Annotated[
        int, typer.Option("--warmup-iterations", help="Warmup iterations")
    ] = 5,
    iterations: Annotated[int, typer.Option(help="Measurement iterations")] = 20,
    time_ms: Annotated[int | None, typer.Option("--time-ms", help="Iteration time in ms")] = None,
) -> None:
    """Run a single benchmark end-to-end.

    Pipeline: detect project → scan → resolve → generate JMH source → build jar →
    run → normalize → print. The resolve/generate/build steps share one error
    handler so any ``ResolutionError``/``BuildError`` becomes a clean ``error:``
    line with exit code 1.
    """
    _check_format(fmt)
    cwd = Path.cwd()
    project = _detect_java_project(cwd)
    if project is None:
        _emit("No Java project detected in the current directory.", fmt)
        raise typer.Exit(code=1)

    adapter = JavaAdapter()
    scan = adapter.scan(cwd)
    benchmark = next((b for b in scan.benchmarks if b.benchmark_name == name), None)
    if benchmark is None:
        available = ", ".join(b.benchmark_name for b in scan.benchmarks) or "(none)"
        _emit(f"Benchmark '{name}' not found. Available: {available}", fmt)
        raise typer.Exit(code=1)

    try:
        resolved = adapter.resolve(benchmark, scan.fixtures, project)
        source = adapter.generate_benchmark(resolved)
        build = adapter.build(cwd, [source])
    except Exception as exc:  # ResolutionError / BuildError
        _emit(f"error: {exc}", fmt)
        raise typer.Exit(code=1) from None

    jmh_args = ["-f", str(forks), "-wi", str(warmup_iterations), "-i", str(iterations)]
    if time_ms is not None:
        jmh_args += ["-w", f"{time_ms}ms", "-r", f"{time_ms}ms"]

    result = adapter.run(build.jar, jmh_args, build.build_dir)
    if result.raw_json is None:
        _emit("error: benchmark run failed:\n" + result.stderr, fmt)
        raise typer.Exit(code=1)

    results = adapter.normalize(result.raw_json)
    for r in results:
        r.experiment_id = name

    if fmt == "json":
        _emit({"results": results}, fmt)
    else:
        _emit(_format_results(results), fmt)


def _format_results(results) -> str:
    """Render a list of ``BenchmarkResult`` as a human-readable multi-line string."""
    lines = []
    for r in results:
        t = r.timing
        median = f"{t.median_ns / 1e6:.3f} ms" if t and t.median_ns else "n/a"
        params = ", ".join(f"{k}={v}" for k, v in r.parameters.items())
        label = f"  [{params}]" if params else ""
        lines.append(f"{r.benchmark_name}{label}  median {median}")
    return "\n".join(lines)
