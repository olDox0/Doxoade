# -*- coding: utf-8 -*-
"""Auto-fix de imports locais quando módulos são movidos."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


_IGNORED_DIRS = {
    ".git", "venv", ".venv", "env", "__pycache__", ".doxoade", ".pytest_cache", "build", "dist"
}


@dataclass
class FixResult:
    files_changed: int
    imports_changed: int
    details: list[str]


def _iter_python_files(root: Path):
    for p in root.rglob("*.py"):
        if any(part in _IGNORED_DIRS for part in p.parts):
            continue
        yield p


def _module_name_for_path(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def collect_local_modules(root: Path) -> set[str]:
    modules: set[str] = set()
    for p in _iter_python_files(root):
        mod = _module_name_for_path(root, p)
        if mod:
            modules.add(mod)
    return modules


def _module_exists(name: str, modules: set[str]) -> bool:
    return name in modules or any(m.startswith(name + ".") for m in modules)


def _best_candidate(old: str, modules: set[str]) -> str | None:
    segs = old.split(".")
    if len(segs) < 2:
        return None

    top = segs[0]
    leaf = segs[-1]
    cands = [m for m in modules if m.split(".")[0] == top and m.split(".")[-1] == leaf]
    if not cands:
        return None

    ranked = sorted(
        ((SequenceMatcher(None, old, cand).ratio(), cand) for cand in cands),
        reverse=True,
    )
    best_score, best = ranked[0]
    if best_score < 0.45:
        return None
    if len(ranked) > 1 and (best_score - ranked[1][0]) < 0.08:
        return None
    return best


def _build_import_stmt(node: ast.stmt, repl: dict[str, str]) -> str | None:
    if isinstance(node, ast.Import):
        names = []
        changed = False
        for a in node.names:
            new_name = repl.get(a.name, a.name)
            changed = changed or (new_name != a.name)
            names.append(new_name + (f" as {a.asname}" if a.asname else ""))
        if not changed:
            return None
        return "import " + ", ".join(names)

    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        new_mod = repl.get(node.module, node.module)
        if new_mod == node.module:
            return None
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
        return f"from {new_mod} import {names}"

    return None


def _replace_segment(src: str, node: ast.stmt, new_stmt: str) -> str:
    lines = src.splitlines(keepends=True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))

    s = starts[node.lineno - 1] + node.col_offset
    e = starts[node.end_lineno - 1] + node.end_col_offset
    indent = " " * node.col_offset
    return src[:s] + indent + new_stmt + src[e:]


def fix_imports_in_file(file_path: Path, modules: set[str]) -> tuple[bool, int, list[str]]:
    src = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False, 0, []

    replacements: dict[ast.stmt, str] = {}
    messages: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        repl: dict[str, str] = {}

        if isinstance(node, ast.Import):
            for a in node.names:
                if _module_exists(a.name, modules):
                    continue
                cand = _best_candidate(a.name, modules)
                if cand:
                    repl[a.name] = cand
                    messages.append(f"{a.name} -> {cand}")

        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if not _module_exists(node.module, modules):
                cand = _best_candidate(node.module, modules)
                if cand:
                    repl[node.module] = cand
                    messages.append(f"{node.module} -> {cand}")

        new_stmt = _build_import_stmt(node, repl)
        if new_stmt:
            replacements[node] = new_stmt

    if not replacements:
        return False, 0, []

    out = src
    for node in sorted(replacements, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        out = _replace_segment(out, node, replacements[node])

    if out != src:
        file_path.write_text(out, encoding="utf-8")
        return True, len(replacements), messages

    return False, 0, []


def fix_project_imports(root: Path) -> FixResult:
    modules = collect_local_modules(root)
    files_changed = 0
    imports_changed = 0
    details: list[str] = []

    for py in _iter_python_files(root):
        changed, n, msgs = fix_imports_in_file(py, modules)
        if changed:
            files_changed += 1
            imports_changed += n
            for m in msgs:
                details.append(f"{py}: {m}")

    return FixResult(files_changed=files_changed, imports_changed=imports_changed, details=details)
