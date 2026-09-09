"""Parameter model, scopes, and generators."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParameterScope(Enum):
    """When a parameter's value changes relative to measurement.

    INVOCATION: the value is supplied to the benchmarked operation itself.
    SETUP:      the value changes fixture/state construction (not timed).
    TRIAL:      the value creates different state per benchmark trial.
    """

    INVOCATION = "invocation"
    SETUP = "setup"
    TRIAL = "trial"


@dataclass
class Generator:
    """A language-specific value generator, e.g. ``randomIntArray(size)``."""

    name: str
    arguments: list[str] = field(default_factory=list)


@dataclass
class Parameter:
    """A single experiment parameter: either a list of values or a generator."""

    name: str
    scope: ParameterScope = ParameterScope.INVOCATION
    values: list[Any] | None = None
    generator: Generator | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("parameter name must not be empty")
        # A parameter must have exactly one source of variation.
        if self.values is None and self.generator is None:
            raise ValueError(f"parameter '{self.name}' needs values or a generator")
        if self.values is not None and self.generator is not None:
            raise ValueError(f"parameter '{self.name}' cannot have both values and a generator")
