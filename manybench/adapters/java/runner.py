"""Run a generated JMH jar and capture results."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class RunError(Exception):
    pass


@dataclass
class RunResult:
    raw_json: list | None
    stdout: str
    stderr: str
    returncode: int


def _find_java() -> str:
    """Locate java on PATH, or raise RunError."""
    java = shutil.which("java")
    if java is None:
        raise RunError("java not found on PATH")
    return java


def run(jar: Path, args: list[str], output_dir: Path) -> RunResult:
    """Execute the JMH jar and return captured output plus the parsed JSON results.

    JMH is asked to write machine-readable JSON via -rf json -rff <path>. If the run
    crashes or the JSON is malformed, raw_json is None (the caller then reports
    failure using stderr).
    """
    java = _find_java()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "results.json"

    cmd = [
        java,
        "-jar",
        str(jar),
        "-rf", "json",
        "-rff", str(json_path),
        *args,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw_json = None
    if json_path.exists():
        try:
            raw_json = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw_json = None
    return RunResult(
        raw_json=raw_json,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )
