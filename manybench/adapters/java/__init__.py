"""Java language adapter — orchestrates javac + JMH."""
from __future__ import annotations

from pathlib import Path

from manybench.adapters import LanguageAdapter
from manybench.adapters.java import builder, detector, generator, parser, runner, scanner
from manybench.adapters.java.resolver import ResolvedExperiment, resolve
from manybench.adapters.java.scanner import ParsedBenchmark, ScanResult
from manybench.core.discovery import Project, ProjectInfo, Routine


class JavaAdapter(LanguageAdapter):
    """Java adapter: orchestrates javac + JMH to benchmark Java routines.

    Implements the LanguageAdapter contract by delegating to the submodules
    (detector, scanner, resolver, generator, builder, runner, parser).
    """

    language = "java"

    def detect(self, project: Path) -> ProjectInfo | None:
        """Return a ProjectInfo if project is a Java project, else None."""
        return detector.detect(Path(project))

    def scan(self, project: Path) -> ScanResult:
        """Scan project for @bench benchmarks and @bench-fixture definitions."""
        return scanner.scan(Path(project))

    def discover_routines(self, project: Path) -> list[Routine]:
        """Map every scanned benchmark to a language-neutral core Routine."""
        result = self.scan(project)
        return [
            Routine(
                name=b.benchmark_name,
                benchmark_name=b.benchmark_name,
                file=b.file,
                language="java",
                symbol=f"{b.class_name}.{b.method_name}",
                line=b.line,
                parameters=[p.name for p in b.params],
            )
            for b in result.benchmarks
        ]

    def resolve(self, benchmark: ParsedBenchmark, fixtures, project: Project) -> ResolvedExperiment:
        """Resolve a parsed benchmark (plus available fixtures) into a codegen plan."""
        return resolve(benchmark, fixtures, project)

    def generate_benchmark(self, experiment) -> str:
        """Render the resolved benchmark into a JMH benchmark source string."""
        return generator.generate(experiment.benchmark)

    def build(self, project: Path, sources: list[str]) -> builder.BuildResult:
        """Compile the benchmark sources and package them into a standalone jar."""
        return builder.build(Path(project), sources)

    def run(self, jar: Path, args: list[str], output_dir: Path) -> runner.RunResult:
        """Run the JMH jar, capturing its JSON output."""
        return runner.run(jar, args, output_dir)

    def normalize(self, raw) -> list:
        """Parse raw JMH JSON into a list of BenchmarkResult."""
        return parser.parse(raw, "")
