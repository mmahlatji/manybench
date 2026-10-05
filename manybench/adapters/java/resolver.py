"""Resolve parsed benchmarks + fixtures into a codegen-ready model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from manybench.adapters.java import java_source
from manybench.adapters.java.scanner import ParsedBenchmark, ParsedFixture
from manybench.core.config import MeasurementConfig, WarmupConfig
from manybench.core.discovery import Project, Routine
from manybench.core.experiments import Experiment
from manybench.core.fixtures import Fixture
from manybench.core.parameters import Generator, Parameter, ParameterScope

GENERATORS: dict[str, tuple[str, list[str]]] = {
    "randomIntArray": ("int[]", ["size"]),
    "sortedIntArray": ("int[]", ["size"]),
    "randomIntList": ("java.util.List<java.lang.Integer>", ["size"]),
}


class ResolutionError(Exception):
    pass


@dataclass
class ParamField:
    """A value parameter mapped to a JMH @Param field."""

    name: str
    type: str
    values: list[str]


@dataclass
class GeneratorField:
    """A generator parameter: a field produced by Generators during @Setup."""

    name: str
    generator: str
    type: str
    args: list[str]


@dataclass
class FixtureRef:
    """A resolved reference to a fixture factory method."""

    name: str
    class_fq: str
    method_name: str
    return_type: str
    args: list[str]


@dataclass
class ResolvedBenchmark:
    """A fully-resolved, codegen-ready description of one benchmark."""

    benchmark_name: str
    java_class_name: str
    target_class_fq: str
    target_method: str
    target_is_static: bool
    param_fields: list[ParamField]
    generator_fields: list[GeneratorField]
    fixture: FixtureRef | None
    target_args: list[str]


@dataclass
class ResolvedExperiment:
    """The resolution output: the codegen plan plus the core Experiment model."""

    experiment: Experiment
    benchmark: ResolvedBenchmark


def _infer_value_type(values: list[str]) -> str:
    """Guess a Java primitive/type for a list of raw @Param values.

    All booleans -> boolean; all integers -> int; all numbers -> double; otherwise
    java.lang.String. Used only when no target/fixture signature provides the type.
    """
    lowered = [v.lower() for v in values]

    def is_int(v: str) -> bool:
        return v.lstrip("+-").isdigit()

    def is_bool(v: str) -> bool:
        return v in {"true", "false"}

    def is_num(v: str) -> bool:
        try:
            float(v)
            return True
        except ValueError:
            return False

    if all(is_bool(v) for v in lowered):
        return "boolean"
    if all(is_int(v) for v in values):
        return "int"
    if all(is_num(v) for v in values):
        return "double"
    return "java.lang.String"


def _coerce_value(value: str):
    """Convert a raw string value into a Python bool/int/float (or leave as string)."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lstrip("+-").isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def resolve(
    benchmark: ParsedBenchmark, fixtures: list[ParsedFixture], project: Project
) -> ResolvedExperiment:
    """Turn a parsed benchmark into a codegen-ready ResolvedBenchmark + core Experiment.

    Responsibilities:
      - validate the target method and locate its fixture (if referenced);
      - decide each @Param field's Java type (fixture types win over target types
        so a setup parameter keeps its fixture type on name collisions);
      - split @bench-param lines into @Param fields vs. generated fields;
      - resolve each target-method argument to a field, a generator result, or the
        fixture result, erroring when nothing matches.
    """
    if not benchmark.is_static and not benchmark.fixture_ref:
        raise ResolutionError(
            f"benchmark '{benchmark.benchmark_name}': instance methods need a @bench-fixture"
        )

    fixture: ParsedFixture | None = None
    if benchmark.fixture_ref:
        match = [f for f in fixtures if f.name == benchmark.fixture_ref]
        if not match:
            raise ResolutionError(
                f"benchmark '{benchmark.benchmark_name}': unknown fixture '{benchmark.fixture_ref}'"
            )
        if len(match) > 1:
            raise ResolutionError(
                f"benchmark '{benchmark.benchmark_name}': multiple fixtures "
                f"named '{benchmark.fixture_ref}'"
            )
        fixture = match[0]
        if not fixture.is_static:
            raise ResolutionError(f"fixture '{fixture.name}' must be static")

    target_jf = benchmark.java_file
    target_class_fq = java_source.resolve_type(
        f"{benchmark.class_name}", target_jf
    )

    param_by_name = {p.name: p for p in benchmark.params}

    # Determine each @Param field's Java type. Fixture-argument types take
    # precedence so that a setup parameter keeps its fixture type even when a
    # target argument shares the same name.
    param_types: dict[str, str] = {}
    if fixture:
        for ftype, fname in fixture.param_types:
            resolved = java_source.resolve_type(ftype, fixture.java_file)
            if fname in param_by_name and param_by_name[fname].generator is None:
                param_types[fname] = resolved
    for ttype, tname in benchmark.param_types:
        if (
            tname in param_by_name
            and param_by_name[tname].generator is None
            and tname not in param_types
        ):
            param_types[tname] = java_source.resolve_type(ttype, target_jf)

    param_fields: list[ParamField] = []
    generator_fields: list[GeneratorField] = []
    parameters: list[Parameter] = []

    for bp in benchmark.params:
        if bp.values is not None:
            jtype = param_types.get(bp.name) or _infer_value_type(bp.values)
            param_fields.append(ParamField(name=bp.name, type=jtype, values=bp.values))
            parameters.append(
                Parameter(
                    name=bp.name,
                    scope=ParameterScope.SETUP,
                    values=[_coerce_value(v) for v in bp.values],
                )
            )
        else:
            gen = GENERATORS.get(bp.generator or "")
            if gen is None:
                raise ResolutionError(
                    f"benchmark '{benchmark.benchmark_name}': unknown generator '{bp.generator}'"
                )
            gen_type, _ = gen
            generator_fields.append(
                GeneratorField(
                    name=bp.name,
                    generator=bp.generator or "",
                    type=gen_type,
                    args=bp.generator_args,
                )
            )
            parameters.append(
                Parameter(
                    name=bp.name,
                    scope=ParameterScope.SETUP,
                    generator=Generator(name=bp.generator or "", arguments=bp.generator_args),
                )
            )

    fixture_ref: FixtureRef | None = None
    if fixture:
        fargs = [fname for _ftype, fname in fixture.param_types]
        fixture_ref = FixtureRef(
            name=fixture.name,
            class_fq=java_source.resolve_type(fixture.class_name, fixture.java_file),
            method_name=fixture.method_name,
            return_type=java_source.resolve_type(fixture.return_type, fixture.java_file),
            args=fargs,
        )

    # Resolve target method arguments. A value param consumed by the fixture is a
    # setup-only parameter and must not be re-matched to a same-named target arg.
    fixture_arg_names = set(fixture_ref.args) if fixture_ref else set()
    target_args: list[str] = []
    for ttype, tname in benchmark.param_types:
        resolved_type = java_source.resolve_type(ttype, target_jf)
        bp = param_by_name.get(tname)
        if bp is not None and bp.generator is not None:
            target_args.append(tname)
        elif (
            bp is not None
            and bp.values is not None
            and tname not in fixture_arg_names
            and param_types.get(tname) == resolved_type
        ):
            target_args.append(tname)
        elif fixture_ref and resolved_type == fixture_ref.return_type:
            target_args.append("__fixture")
        else:
            raise ResolutionError(
                f"benchmark '{benchmark.benchmark_name}': cannot resolve argument '{tname} "
                f"({ttype}); declare a matching @bench-param or @bench-fixture"
            )

    java_class_name = _to_pascal(benchmark.benchmark_name) + "Benchmark"
    resolved_benchmark = ResolvedBenchmark(
        benchmark_name=benchmark.benchmark_name,
        java_class_name=java_class_name,
        target_class_fq=target_class_fq,
        target_method=benchmark.method_name,
        target_is_static=benchmark.is_static,
        param_fields=param_fields,
        generator_fields=generator_fields,
        fixture=fixture_ref,
        target_args=target_args,
    )

    routine = Routine(
        name=benchmark.benchmark_name,
        benchmark_name=benchmark.benchmark_name,
        file=Path(benchmark.file),
        language="java",
        symbol=f"{benchmark.class_name}.{benchmark.method_name}",
        line=benchmark.line,
        parameters=[p.name for p in benchmark.params],
    )
    experiment = Experiment(
        id=benchmark.benchmark_name,
        name=benchmark.benchmark_name,
        project=project,
        target=routine,
        fixture=Fixture(name=fixture.name, symbol=fixture.method_name) if fixture else None,
        parameters=parameters,
        warmup=WarmupConfig(),
        measurement=MeasurementConfig(),
    )
    return ResolvedExperiment(experiment=experiment, benchmark=resolved_benchmark)


def _to_pascal(name: str) -> str:
    """Convert a kebab/snake-case benchmark name to PascalCase.

    physics-step -> PhysicsStep; empty input falls back to Benchmark.
    """
    parts = [p for p in name.replace("_", "-").split("-") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Benchmark"
