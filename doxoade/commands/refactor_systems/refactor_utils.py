from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


try:
    from doxoade.tools.filesystem import SYSTEM_IGNORES as _SYSTEM_IGNORES
except ImportError:
    _SYSTEM_IGNORES: set[str] = set()

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__",
    "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox",
    ".venv", "venv", "env",
    "build", "dist",
} | {s.lower() for s in _SYSTEM_IGNORES}


@dataclass(frozen=True)
class FunctionHit:
    name: str
    file: Path
    line: int
    col: int
    kind: str = "def"
    qualname: str | None = None


@dataclass(frozen=True)
class ReferenceHit:
    name: str
    file: Path
    line: int
    col: int
    context: str = "usage"


def normalize_name(name: str) -> str:
    return name.strip()


def is_python_file(path: Path) -> bool:
    return path.is_file() and path.suffix == ".py"


def iter_python_files(root: Path) -> Iterator[Path]:
    root = root.resolve()

    for current, dirs, files in os.walk(root):
        current_path = Path(current)

        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".venv")]

        if current_path.name in SKIP_DIRS:
            dirs[:] = []
            continue

        for filename in files:
            path = current_path / filename
            if is_python_file(path):
                yield path


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except OSError:
        return ""


def parse_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(read_text_safe(path), filename=str(path))
    except SyntaxError:
        return None
    except Exception:
        return None


class _FunctionCollector(ast.NodeVisitor):
    def __init__(self, file: Path) -> None:
        self.file = file
        self.hits: list[FunctionHit] = []
        self.scope_stack: list[str] = []

    def _qualname(self, name: str) -> str | None:
        if not self.scope_stack:
            return name
        return ".".join((*self.scope_stack, name))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.hits.append(
            FunctionHit(
                name=node.name,
                file=self.file,
                line=getattr(node, "lineno", 0),
                col=getattr(node, "col_offset", 0),
                kind="def",
                qualname=self._qualname(node.name),
            )
        )
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.hits.append(
            FunctionHit(
                name=node.name,
                file=self.file,
                line=getattr(node, "lineno", 0),
                col=getattr(node, "col_offset", 0),
                kind="async def",
                qualname=self._qualname(node.name),
            )
        )
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()


class _ReferenceCollector(ast.NodeVisitor):
    def __init__(self, file: Path, targets: set[str]) -> None:
        self.file = file
        self.targets = targets
        self.hits: list[ReferenceHit] = []

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.targets:
            self.hits.append(
                ReferenceHit(
                    name=node.id,
                    file=self.file,
                    line=getattr(node, "lineno", 0),
                    col=getattr(node, "col_offset", 0),
                )
            )
        self.generic_visit(node)


def collect_function_defs(path: Path) -> list[FunctionHit]:
    tree = parse_ast(path)
    if tree is None:
        return []

    collector = _FunctionCollector(path)
    collector.visit(tree)
    return collector.hits


def collect_references(path: Path, target_names: Iterable[str]) -> list[ReferenceHit]:
    tree = parse_ast(path)
    if tree is None:
        return []

    targets = {normalize_name(name) for name in target_names if normalize_name(name)}
    collector = _ReferenceCollector(path, targets)
    collector.visit(tree)
    return collector.hits


def find_functions_in_path(path: Path, target_names: Iterable[str]) -> dict[str, list[FunctionHit]]:
    path = path.resolve()
    targets = {normalize_name(name) for name in target_names if normalize_name(name)}
    found: dict[str, list[FunctionHit]] = {name: [] for name in targets}

    if path.is_file():
        for hit in collect_function_defs(path):
            if hit.name in targets:
                found[hit.name].append(hit)
        return found

    for py_file in iter_python_files(path):
        for hit in collect_function_defs(py_file):
            if hit.name in targets:
                found[hit.name].append(hit)

    return found


def find_references_in_path(path: Path, target_names: Iterable[str]) -> dict[str, list[ReferenceHit]]:
    path = path.resolve()
    targets = {normalize_name(name) for name in target_names if normalize_name(name)}
    found: dict[str, list[ReferenceHit]] = {name: [] for name in targets}

    if path.is_file():
        for hit in collect_references(path, targets):
            found[hit.name].append(hit)
        return found

    for py_file in iter_python_files(path):
        for hit in collect_references(py_file, targets):
            found[hit.name].append(hit)

    return found