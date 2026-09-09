"""Fixture model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fixture:
    """A named piece of setup state constructed before measurement."""

    name: str
    symbol: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("fixture name must not be empty")
