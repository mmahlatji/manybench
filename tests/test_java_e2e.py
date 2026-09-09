import shutil
from pathlib import Path

import pytest

from polybench.adapters.java import JavaAdapter
from polybench.core.discovery import Project

SAMPLE = Path(__file__).parent / "java_project"


def _resolve(name: str):
    adapter = JavaAdapter()
    project = Project(path=SAMPLE, language="java", build_system="javac")
    scan = adapter.scan(SAMPLE)
    benchmark = next(b for b in scan.benchmarks if b.benchmark_name == name)
    return adapter.resolve(benchmark, scan.fixtures, project)


def test_resolve_simple() -> None:
    resolved = _resolve("physics-step")
    b = resolved.benchmark
    assert b.target_class_fq == "benchdemo.Physics"
    assert b.target_method == "step"
    assert len(b.param_fields) == 1
    assert b.param_fields[0].name == "n"
    assert b.param_fields[0].values == ["1000", "10000"]
    assert b.fixture is None
    assert b.target_args == ["n"]


def test_resolve_with_fixture() -> None:
    resolved = _resolve("check-collisions")
    b = resolved.benchmark
    assert b.fixture is not None
    assert b.fixture.class_fq == "benchdemo.Physics"
    assert b.fixture.method_name == "createParticles"
    assert b.fixture.args == ["particles"]
    assert b.target_args == ["__fixture", "subSteps"]


def test_generated_source_compiles_shape() -> None:
    from polybench.adapters.java import generator

    resolved = _resolve("check-collisions")
    source = generator.generate(resolved.benchmark)
    assert "public class CheckCollisionsBenchmark" in source
    assert "import org.openjdk.jmh.annotations.Level;" in source
    assert "@org.openjdk.jmh.annotations.Param" in source
    assert "__fixture = benchdemo.Physics.createParticles(particles);" in source
    assert "benchdemo.Physics.checkCollisions(__fixture, subSteps);" in source


@pytest.mark.e2e
def test_end_to_end_run() -> None:
    if shutil.which("java") is None or shutil.which("javac") is None:
        pytest.skip("java/javac not available")

    adapter = JavaAdapter()
    project = Project(path=SAMPLE, language="java", build_system="javac")
    scan = adapter.scan(SAMPLE)
    benchmark = next(b for b in scan.benchmarks if b.benchmark_name == "physics-step")

    resolved = adapter.resolve(benchmark, scan.fixtures, project)
    source = adapter.generate_benchmark(resolved)
    build = adapter.build(SAMPLE, [source])

    result = adapter.run(
        build.jar,
        ["-f", "1", "-wi", "2", "-i", "2", "-w", "100ms", "-r", "100ms"],
        build.build_dir,
    )
    assert result.raw_json is not None, result.stderr
    results = adapter.normalize(result.raw_json)
    assert len(results) == 2
    assert {r.parameters.get("n") for r in results} == {1000, 10000}
    assert all(r.timing is not None and r.timing.median_ns is not None for r in results)

    shutil.rmtree(build.build_dir, ignore_errors=True)
