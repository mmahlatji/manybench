from pathlib import Path

from polybench.adapters.java import detector, java_source, scanner

SAMPLE = Path(__file__).parent / "java_project"


def test_detect_java_project() -> None:
    info = detector.detect(SAMPLE)
    assert info is not None
    assert info.language == "java"
    assert info.build_system == "javac"


def test_detect_non_java(tmp_path) -> None:
    assert detector.detect(tmp_path) is None


def test_parse_method() -> None:
    sig = java_source.parse_method(
        "public static void checkCollisions(List<Integer> particles, int subSteps) {"
    )
    assert sig is not None
    assert sig.name == "checkCollisions"
    assert sig.is_static is True
    assert sig.return_type == "void"
    assert sig.params == [("List<Integer>", "particles"), ("int", "subSteps")]


def test_parse_method_generic_return() -> None:
    sig = java_source.parse_method("public static List<Integer> createParticles(int particles) {")
    assert sig is not None
    assert sig.name == "createParticles"
    assert sig.return_type == "List<Integer>"


def test_resolve_type_import() -> None:
    jf = java_source.parse_file("x.java", "package benchdemo;\nimport java.util.List;\n")
    assert java_source.resolve_type("List<Integer>", jf) == "java.util.List<java.lang.Integer>"


def test_scan_benchmarks() -> None:
    result = scanner.scan(SAMPLE)
    names = [b.benchmark_name for b in result.benchmarks]
    assert "physics-step" in names
    assert "check-collisions" in names

    collisions = next(b for b in result.benchmarks if b.benchmark_name == "check-collisions")
    assert collisions.is_static is True
    assert collisions.fixture_ref == "createParticles"
    param_names = [p.name for p in collisions.params]
    assert param_names == ["particles", "subSteps"]

    fixtures = [f.name for f in result.fixtures]
    assert "createParticles" in fixtures
