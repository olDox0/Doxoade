# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_verify.py
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class VerifyIssue:
    file: Path
    line: int
    kind: str  # MISSING_IMPORT | WRONG_IMPORT | OK | MULTIPLE_IMPORTS
    detail: str


@dataclass(frozen=True)
class VerifyResult:
    root: Path
    function_name: str
    expected_import: str
    issues: List[VerifyIssue] = field(default_factory=list)


def _iter_py_files(root: Path):
    try:
        from doxoade.tools.filesystem import SYSTEM_IGNORES
        skip = {s.lower() for s in SYSTEM_IGNORES}
    except ImportError:
        skip = {"__pycache__", ".doxoade", ".doxoade_cache", ".dox_agent_workspace", ".git", ".venv", "venv", "env", "node_modules"}

    for p in root.rglob("*.py"):
        if any(part.lower() in skip or part.startswith(".") for part in p.parts):
            continue
        yield p


def _parse_file(path: Path) -> Tuple[ast.AST | None, List[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(text), text.splitlines()
    except Exception:
        return None, []


def _find_function_usages(tree: ast.AST, function_name: str) -> List[int]:
    lines = []
    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name):
            if node.id == function_name and isinstance(getattr(node, "ctx", None), ast.Load):
                lines.append(getattr(node, "lineno", 0))
            self.generic_visit(node)
        def visit_Attribute(self, node: ast.Attribute):
            if node.attr == function_name and isinstance(getattr(node, "ctx", None), ast.Load):
                lines.append(getattr(node, "lineno", 0))
            self.generic_visit(node)
    Visitor().visit(tree)
    return sorted(list(set(l for l in lines if l > 0)))


def _find_imports(tree: ast.AST, function_name: str) -> List[Tuple[str, str, int]]:
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == function_name or getattr(alias, "asname", None) == function_name:
                    imports.append((node.module or "", alias.name, getattr(node, "lineno", 0)))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == function_name or getattr(alias, "asname", None) == function_name:
                    imports.append((alias.name, getattr(alias, "asname", None) or alias.name, getattr(node, "lineno", 0)))
    return imports


def _is_function_defined(tree: ast.AST, function_name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == function_name:
                return True
    return False


def verify_imports(root: Path, function_name: str, expected_module: str) -> VerifyResult:
    root = root.resolve()
    expected_import = f"from {expected_module} import {function_name}"
    issues: List[VerifyIssue] = []

    for file_path in _iter_py_files(root):
        tree, _ = _parse_file(file_path)
        if tree is None:
            continue

        usages = _find_function_usages(tree, function_name)
        defined_here = _is_function_defined(tree, function_name)
        imports = _find_imports(tree, function_name)

        if defined_here:
            if imports:
                for module, _, lineno in imports:
                    issues.append(VerifyIssue(file_path, lineno, "WRONG_IMPORT", "Import desnecessário na própria fonte"))
            continue

        if not usages:
            if imports:
                for module, _, lineno in imports:
                    if module != expected_module:
                        issues.append(VerifyIssue(file_path, lineno, "WRONG_IMPORT", "Import antigo em arquivo sem uso"))
                    else:
                        if file_path.name != "__init__.py":
                            issues.append(VerifyIssue(file_path, lineno, "WRONG_IMPORT", "Import sem uso"))
            continue

        if not imports:
            for line in usages:
                issues.append(VerifyIssue(file_path, line, "MISSING_IMPORT", "Função usada sem import"))
            continue

        if len(imports) > 1:
            for module, _, lineno in imports:
                issues.append(VerifyIssue(file_path, lineno, "MULTIPLE_IMPORTS", f"Import múltiplo de {function_name} ({module})"))
            continue

        module, _, lineno = imports[0]

        if module != expected_module:
            issues.append(VerifyIssue(file_path, lineno, "WRONG_IMPORT", f"Importando de '{module}', esperado '{expected_module}'"))
            continue

        issues.append(VerifyIssue(file_path, lineno, "OK", "Import correto"))

    return VerifyResult(root, function_name, expected_import, issues)


def find_import_insertion_point(tree: ast.AST) -> int:
    insert_line = 0
    body = getattr(tree, "body", [])
    if not body:
        return 0

    idx = 0
    if isinstance(body[idx], ast.Expr) and isinstance(getattr(body[idx].value, "value", None), str):
        insert_line = getattr(body[idx], "end_lineno", 1)
        idx += 1

    while idx < len(body):
        node = body[idx]
        if isinstance(node, ast.ImportFrom) and getattr(node, "module", "") == "__future__":
            insert_line = getattr(node, "end_lineno", insert_line)
            idx += 1
        else:
            break

    last_import_line = insert_line
    # Limita apenas a nós Globais (top-level)
    for node in body[idx:]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_import_line = max(last_import_line, getattr(node, "end_lineno", last_import_line))
        else:
            break

    return last_import_line


def fix_imports(file_path: Path, target: str, expected_module: str):
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except Exception:
        return  # O arquivo já possui erros de sintaxe graves, não arriscamos modificar.

    defined_here = _is_function_defined(tree, target)
    expected_import = f"from {expected_module} import {target}"
    usages = _find_function_usages(tree, target)
    
    nodes_to_replace = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == target for alias in node.names):
                nodes_to_replace.append(node)
        elif isinstance(node, ast.Import):
            if any(alias.name == target for alias in node.names):
                nodes_to_replace.append(node)

    had_import = len(nodes_to_replace) > 0
    is_init = file_path.name == "__init__.py"
    
    # Apenas injeta se há usos e se não é onde a função reside.
    needs_import = (not defined_here) and (len(usages) > 0 or (is_init and had_import))

    lines = text.splitlines()
    nodes_to_replace.sort(key=lambda n: getattr(n, 'lineno', 1), reverse=True)

    for node in nodes_to_replace:
        start = node.lineno - 1
        end = getattr(node, 'end_lineno', node.lineno)
        
        if isinstance(node, ast.ImportFrom):
            new_aliases = [alias for alias in node.names if alias.name != target]
            if not new_aliases:
                del lines[start:end]
            else:
                indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
                alias_strs = [a.name + (f" as {a.asname}" if getattr(a, "asname", None) else "") for a in new_aliases]
                mod = node.module or ""
                level = getattr(node, "level", 0)
                prefix = "." * level
                new_stmt = f"{indent}from {prefix}{mod} import {', '.join(alias_strs)}"
                lines[start:end] = [new_stmt]
                
        elif isinstance(node, ast.Import):
            new_aliases = [alias for alias in node.names if alias.name != target]
            if not new_aliases:
                del lines[start:end]
            else:
                indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
                alias_strs = [a.name + (f" as {a.asname}" if getattr(a, "asname", None) else "") for a in new_aliases]
                new_stmt = f"{indent}import {', '.join(alias_strs)}"
                lines[start:end] = [new_stmt]

    if needs_import:
        text_without_target = "\n".join(lines)
        try:
            tree2 = ast.parse(text_without_target)
            insert_idx = find_import_insertion_point(tree2)
        except Exception:
            insert_idx = 0
            
        if expected_import not in lines:
            lines.insert(insert_idx, expected_import)

    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_and_fix(root: Path, function_name: str, expected_module: str) -> VerifyResult:
    result = verify_imports(root, function_name, expected_module)
    files_to_fix = {issue.file for issue in result.issues if issue.kind != "OK"}
    
    for file_path in files_to_fix:
        fix_imports(file_path, function_name, expected_module)
        
    return verify_imports(root, function_name, expected_module)