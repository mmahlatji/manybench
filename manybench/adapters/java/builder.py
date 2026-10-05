"""Compile generated benchmarks and build a standalone JMH jar."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from manybench.adapters.java import generator, jmh


class BuildError(Exception):
    pass


@dataclass
class BuildResult:
    jar: Path
    classes_dir: Path
    build_dir: Path


_CLASS_NAME_RE = re.compile(r"public\s+class\s+([A-Za-z_$][\w$]*)")


def _find_javac() -> str:
    """Locate javac on PATH, or raise BuildError with a helpful message."""
    javac = shutil.which("javac")
    if javac is None:
        raise BuildError("javac not found on PATH; install a JDK to build benchmarks")
    return javac


def _source_root(project: Path) -> Path:
    """Return the directory whose subfolders map to Java packages.

    Prefers project/src (the common convention); otherwise falls back to the project
    root. This is used as javac's -sourcepath.
    """
    src = project / "src"
    if src.is_dir():
        return src
    return project


def build(project: Path, benchmark_sources: list[str]) -> BuildResult:
    """Compile the generated benchmarks and package them into a standalone JMH jar.

    Steps:
      1. ensure the JMH jars are cached (downloading on first use);
      2. write the generated sources into a throwaway build dir (each file named
         after its public class, since Java requires the filename to match);
      3. run javac with the JMH annotation processor on the classpath and the
         project source root on -sourcepath; this lets javac implicitly compile only
         the user classes the benchmark references, not the whole project;
      4. verify the processor produced META-INF/BenchmarkList;
      5. assemble benchmarks.jar with a manifest pointing at the JMH jars via
         Class-Path.
    """
    javac = _find_javac()
    jars = jmh.ensure_jars()
    classpath = [str(p) for p in jars]

    build_dir = Path(tempfile.mkdtemp(prefix="manybench-build-"))
    gen_dir = build_dir / "gen" / "manybench" / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    classes_dir = build_dir / "classes"
    classes_dir.mkdir()

    for source in benchmark_sources:
        match = _CLASS_NAME_RE.search(source)
        if match is None:
            raise BuildError("generated benchmark source has no public class")
        (gen_dir / f"{match.group(1)}.java").write_text(source, encoding="utf-8")
    (gen_dir / "Generators.java").write_text(generator.generate_generators(), encoding="utf-8")

    source_root = _source_root(project)
    gen_files = [str(p) for p in gen_dir.glob("*.java")]
    cmd = [
        javac,
        "-cp", ":".join(classpath),
        "-sourcepath", str(source_root),
        "-d", str(classes_dir),
        "-processor", "org.openjdk.jmh.generators.BenchmarkProcessor",
        *gen_files,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError(f"javac failed:\n{proc.stdout}\n{proc.stderr}")

    benchmark_list = classes_dir / "META-INF" / "BenchmarkList"
    if not benchmark_list.exists():
        raise BuildError("JMH annotation processor did not produce META-INF/BenchmarkList")

    manifest = build_dir / "MANIFEST.MF"
    manifest.write_text(
        "Manifest-Version: 1.0\n"
        f"Main-Class: org.openjdk.jmh.Main\n"
        f"Class-Path: {' '.join(classpath)}\n",
        encoding="utf-8",
    )
    jar = build_dir / "benchmarks.jar"
    jar_cmd = ["jar", "cfm", str(jar), str(manifest), "-C", str(classes_dir), "."]
    proc = subprocess.run(jar_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError(f"jar failed:\n{proc.stdout}\n{proc.stderr}")

    return BuildResult(jar=jar, classes_dir=classes_dir, build_dir=build_dir)
