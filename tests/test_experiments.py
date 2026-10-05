from pathlib import Path

import pytest

from manybench.core.experiments import Experiment
from manybench.core.fixtures import Fixture
from manybench.core.parameters import Parameter, ParameterScope


def test_experiment_defaults() -> None:
    from manybench.core.discovery import Project, Routine

    project = Project(path=Path("."), language="java")
    routine = Routine(
        name="physics-step",
        benchmark_name="physics-step",
        file=Path("src/Main.java"),
        language="java",
        symbol="step",
        line=10,
        parameters=[],
    )
    experiment = Experiment(id="e1", name="physics-step", project=project, target=routine)
    assert experiment.warmup.iterations == 5
    assert experiment.measurement.iterations == 20
    assert experiment.parameters == []


def test_parameter_requires_values_or_generator() -> None:
    with pytest.raises(ValueError):
        Parameter(name="particles")


def test_parameter_rejects_both() -> None:
    from manybench.core.parameters import Generator

    with pytest.raises(ValueError):
        Parameter(name="particles", values=[1, 2], generator=Generator(name="randomIntArray"))


def test_parameter_scopes() -> None:
    p = Parameter(name="size", scope=ParameterScope.SETUP, values=[100, 1000])
    assert p.scope is ParameterScope.SETUP


def test_fixture_requires_name() -> None:
    with pytest.raises(ValueError):
        Fixture(name="")
