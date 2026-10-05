"""Generate JMH benchmark source from a resolved benchmark."""
from __future__ import annotations

from manybench.adapters.java.resolver import ResolutionError, ResolvedBenchmark

GENERATED_PACKAGE = "manybench.generated"

_GENERATORS_TEMPLATE = """package {package};

import java.util.Random;

public final class Generators {{
    private Generators() {{}}

    public static int[] randomIntArray(int size) {{
        Random r = new Random(42);
        int[] a = new int[size];
        for (int i = 0; i < size; i++) a[i] = r.nextInt();
        return a;
    }}

    public static int[] sortedIntArray(int size) {{
        int[] a = randomIntArray(size);
        java.util.Arrays.sort(a);
        return a;
    }}

    public static java.util.List<Integer> randomIntList(int size) {{
        java.util.List<Integer> list = new java.util.ArrayList<>(size);
        for (int v : randomIntArray(size)) list.add(v);
        return list;
    }}
}}
"""

_BENCHMARK_TEMPLATE = """package {package};

import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.infra.Blackhole;

import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@State(Scope.Benchmark)
public class {class_name} {{
{param_fields}
{generator_fields}
{fixture_field}

{setup_method}

    @Benchmark
    public void {benchmark_method}(Blackhole bh) {{
        {invoke}
    }}
}}
"""


def generate(benchmark: ResolvedBenchmark) -> str:
    """Render a ResolvedBenchmark into a complete JMH benchmark .java source."""
    return _render_benchmark(benchmark)


def generate_generators() -> str:
    """Return the source for the shared Generators helper class.

    This class is always emitted alongside the benchmark so that generator-backed
    @bench-param lines have concrete implementations to call in @Setup.
    """
    return _GENERATORS_TEMPLATE.format(package=GENERATED_PACKAGE)


def _render_benchmark(b: ResolvedBenchmark) -> str:
    """Assemble the JMH class body from the resolved benchmark fields.

    Non-obvious details:
      - @Param values are emitted as bare strings inside {} because JMH parses them
        itself and converts them to the field type;
      - the fixture result is stored in a private field __fixture assigned in
        @Setup(Level.Trial) so construction is never part of the timed region;
      - benchmark method names have - replaced with _ (JMH/Java identifiers cannot
        contain hyphens).
    """
    param_field_lines: list[str] = []
    for pf in b.param_fields:
        values = ", ".join(f'"{v}"' for v in pf.values)
        param_field_lines.append(f"    @org.openjdk.jmh.annotations.Param({{{values}}})")
        param_field_lines.append(f"    public {pf.type} {pf.name};")

    generator_field_lines: list[str] = []
    for gf in b.generator_fields:
        generator_field_lines.append(f"    private {gf.type} {gf.name};")

    fixture_field_lines: list[str] = []
    setup_lines: list[str] = []
    if b.fixture:
        fixture_field_lines.append(f"    private {b.fixture.return_type} __fixture;")
        for arg in b.fixture.args:
            if arg not in {pf.name for pf in b.param_fields}:
                raise ResolutionError(
                    f"fixture '{b.fixture.name}' argument '{arg}' has no matching @bench-param"
                )
        args = ", ".join(b.fixture.args)
        setup_lines.append(
            f"        __fixture = {b.fixture.class_fq}.{b.fixture.method_name}({args});"
        )

    for gf in b.generator_fields:
        args = ", ".join(gf.args)
        setup_lines.append(f"        {gf.name} = Generators.{gf.generator}({args});")

    setup_method = ""
    if setup_lines:
        setup_method = "\n".join(
            [
                "    @Setup(Level.Trial)",
                "    public void setup() {",
                *setup_lines,
                "    }",
            ]
        )

    args_expr = ", ".join(b.target_args)
    if b.target_is_static:
        invoke = f"{b.target_class_fq}.{b.target_method}({args_expr});"
    else:
        if not b.fixture:
            raise ResolutionError(
                f"benchmark '{b.benchmark_name}' requires a fixture for an instance method"
            )
        invoke = f"__fixture.{b.target_method}({args_expr});"

    return _BENCHMARK_TEMPLATE.format(
        package=GENERATED_PACKAGE,
        class_name=b.java_class_name,
        param_fields="\n".join(param_field_lines),
        generator_fields="\n".join(generator_field_lines),
        fixture_field="\n".join(fixture_field_lines),
        setup_method=setup_method,
        benchmark_method=b.benchmark_name.replace("-", "_"),
        invoke=invoke,
    )
