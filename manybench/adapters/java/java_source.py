"""Helpers for parsing Java source (methods, imports, type resolution)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_MODIFIERS = {"public", "private", "protected", "static", "final", "synchronized",
              "abstract", "native", "default", "strictfp", "transient", "volatile"}

_PRIMITIVES = {"int", "long", "double", "float", "boolean", "byte", "short", "char", "void"}

_JAVA_LANG = {
    "String", "Object", "Integer", "Long", "Double", "Float", "Boolean", "Byte",
    "Short", "Character", "Math", "System", "Runtime", "Thread", "Exception",
    "Override", "SuppressWarnings", "Deprecated", "FunctionalInterface",
}

_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


@dataclass
class MethodSig:
    """A parsed method declaration: name, return type, params, and modifiers."""

    name: str
    return_type: str
    params: list[tuple[str, str]]  # (type, name)
    is_static: bool
    modifiers: set[str] = field(default_factory=set)


@dataclass
class JavaFile:
    """The package and import context of a parsed Java source file."""

    path: str
    package: str = ""
    imports: dict[str, str] = field(default_factory=dict)
    wildcard_imports: list[str] = field(default_factory=list)


def _split_top_level(text: str, separator: str = ",") -> list[str]:
    """Split text on separator occurrences not nested in <> or ().

    Used to split generic parameter lists (Map<String, Integer>, int) without
    breaking on commas inside angle brackets or parentheses.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "<(":
            depth += 1
        elif char in ">)":
            depth = max(0, depth - 1)
        if char == separator and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_method(declaration: str) -> MethodSig | None:
    """Parse a single-line method declaration into a MethodSig.

    Handles modifiers, generic return types (Map<String, Integer> m()) and
    generic/array parameters. Returns None if the line is not a plain method
    declaration (e.g. a field, constructor, or nested annotation).
    """
    line = declaration.split("{", 1)[0].strip()
    line = line.split(";")[0].strip()
    if "throws" in line:
        # Strip a trailing throws clause after the closing paren.
        close = line.rfind(")")
        if close != -1 and close < len(line) - 1:
            line = line[: close + 1].strip()

    open_paren = line.find("(")
    close_paren = line.rfind(")")
    if open_paren == -1 or close_paren == -1:
        return None

    head = line[:open_paren].strip()
    params_str = line[open_paren + 1 : close_paren]

    # The method name is the last identifier before the opening paren; everything
    # before it is modifiers + return type (which may contain spaces in generics).
    name = head.rsplit(None, 1)[-1]
    if not _IDENTIFIER.match(name):
        return None
    rest = head[: -len(name)].strip()

    words = rest.split()
    modifiers: set[str] = set()
    i = 0
    while i < len(words) and words[i] in _MODIFIERS:
        modifiers.add(words[i])
        i += 1
    return_type = " ".join(words[i:]).strip()

    params: list[tuple[str, str]] = []
    if params_str.strip():
        for piece in _split_top_level(params_str):
            piece = piece.strip()
            if not piece:
                continue
            if piece.startswith("final "):
                piece = piece[len("final "):].strip()
            pname = piece.rsplit(None, 1)[-1]
            ptype = piece[: -len(pname)].strip() if piece != pname else ""
            if not _IDENTIFIER.match(pname) or not ptype:
                return None
            params.append((ptype, pname))

    return MethodSig(
        name=name,
        return_type=return_type,
        params=params,
        is_static="static" in modifiers,
        modifiers=modifiers,
    )


def parse_package(line: str) -> str | None:
    """Extract the package name from a package declaration line, if present."""
    match = re.search(r"\bpackage\s+([A-Za-z_$.][A-Za-z0-9_$.]*)", line)
    return match.group(1) if match else None


def parse_import(line: str) -> tuple[str, str] | None:
    """Extract (SimpleName, f.q.Name) from a single-type import line.

    Returns None for wildcard or static imports (handled separately / ignored).
    """
    match = re.search(r"\bimport\s+(?:static\s+)?([A-Za-z_$.][A-Za-z0-9_$.]*)", line)
    if not match:
        return None
    imported = match.group(1)
    if imported.endswith(".*"):
        return None  # handled as wildcard separately
    simple = imported.rsplit(".", 1)[-1]
    return simple, imported


def parse_wildcard_import(line: str) -> str | None:
    """Extract the package prefix from a wildcard import (import a.b.*)."""
    match = re.search(r"\bimport\s+([A-Za-z_$.][A-Za-z0-9_$.]*\.\*)", line)
    return match.group(1)[:-2] if match else None


def parse_file(path: str, text: str) -> JavaFile:
    """Parse a Java file's package and import declarations into a JavaFile."""
    jf = JavaFile(path=path)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("import") and not stripped.startswith("package"):
            continue
        if stripped.startswith("package"):
            pkg = parse_package(stripped)
            if pkg:
                jf.package = pkg
            continue
        wildcard = parse_wildcard_import(stripped)
        if wildcard:
            jf.wildcard_imports.append(wildcard)
            continue
        imp = parse_import(stripped)
        if imp:
            jf.imports[imp[0]] = imp[1]
    return jf


def resolve_type(type_str: str, jf: JavaFile) -> str:
    """Resolve a source type string to a fully-qualified name.

    Generated code uses fully-qualified names everywhere (so it needs no imports),
    hence this mapping: primitives pass through, arrays and generics recurse,
    java.lang names are prefixed, imported names use their import, and anything else
    is assumed to live in the file's own package.
    """
    type_str = type_str.strip()
    if type_str in _PRIMITIVES:
        return type_str
    if type_str.endswith("[]"):
        return resolve_type(type_str[:-2], jf) + "[]"
    if "<" in type_str:
        base, _, args = type_str.partition("<")
        args = args.rstrip(">")
        resolved_args = ", ".join(resolve_type(a.strip(), jf) for a in _split_top_level(args))
        return f"{resolve_type(base, jf)}<{resolved_args}>"
    if type_str in _JAVA_LANG:
        return f"java.lang.{type_str}"
    if type_str in jf.imports:
        return jf.imports[type_str]
    if jf.package:
        return f"{jf.package}.{type_str}"
    return type_str
