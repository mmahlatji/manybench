"""Manage the JMH dependency jars (download + cache from Maven Central)."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

JMH_VERSION = "1.37"

_ARTIFACTS = [
    ("org/openjdk/jmh", "jmh-core", "jar"),
    ("org/openjdk/jmh", "jmh-generator-annprocess", "jar"),
    ("net/sf/jopt-simple", "jopt-simple", "jar"),
    ("org/apache/commons", "commons-math3", "jar"),
]

# non-JMH dependencies pulled in for completeness of the runtime classpath
_VERSIONS = {
    "jopt-simple": "5.0.4",
    "commons-math3": "3.6.1",
}

_MAVEN_BASE = "https://repo1.maven.org/maven2"


def _cache_dir() -> Path:
    """Return the cache directory holding downloaded JMH jars for this version."""
    base = os.environ.get("MANYBENCH_CACHE", os.path.expanduser("~/.cache/manybench"))
    return Path(base) / "jmh" / JMH_VERSION


def _artifact_path(group: str, name: str) -> Path:
    """Return the on-disk path for a given artifact, using its pinned version."""
    version = _VERSIONS.get(name, JMH_VERSION)
    return _cache_dir() / f"{name}-{version}.jar"


def _download(group: str, name: str) -> Path:
    """Download one artifact from Maven Central into the cache, atomically.

    Writes to a .part temp file then renames it into place so a partial download can
    never be mistaken for a complete jar.
    """
    version = _VERSIONS.get(name, JMH_VERSION)
    url = f"{_MAVEN_BASE}/{group}/{name}/{version}/{name}-{version}.jar"
    dest = _artifact_path(group, name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".jar.part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as out:
        out.write(resp.read())
    tmp.replace(dest)
    return dest


def ensure_jars() -> list[Path]:
    """Return the JMH classpath jars, downloading any that are missing from the cache."""
    jars: list[Path] = []
    for group, name, _packaging in _ARTIFACTS:
        path = _artifact_path(group, name)
        if not path.exists():
            path = _download(group, name)
        jars.append(path)
    return jars


def classpath() -> str:
    """Return the JMH classpath joined with the platform path separator."""
    return os.pathsep.join(str(p) for p in ensure_jars())
