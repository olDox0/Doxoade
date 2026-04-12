# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_verify.py
from __future__ import annotations

import os
import ast

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


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
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _parse_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(text), text.splitlines()
    except Exception:
        return None, []


def _find_function_usages(tree: ast.AST, function_name: str) -> List[int]:
    lines = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == function_name:
                lines.append(node.lineno)
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == function_name:
                    lines.append(node.lineno)
            self.generic_visit(node)

    Visitor().visit(tree)
    return lines


def _find_imports(tree: ast.AST, function_name: str):
    imports = []

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == function_name:
                    imports.append((
                        node.module,
                        alias.name,
                        getattr(node, "lineno", 0)
                    ))

    return imports


def verify_imports(root: Path, function_name: str, expected_module: str) -> VerifyResult:
    root = root.resolve()
    expected_import = f"from {expected_module} import {function_name}"

    issues: List[VerifyIssue] = []

    for file_path in _iter_py_files(root):
        tree, lines = _parse_file(file_path)
        if tree is None:
            continue

        usages = _find_function_usages(tree, function_name)
        if not usages:
            continue

        imports = _find_imports(tree, function_name)

        # Nenhum import encontrado
        if not imports:
            for line in usages:
                issues.append(VerifyIssue(
                    file=file_path,
                    line=line,
                    kind="MISSING_IMPORT",
                    detail="Função usada sem import"
                ))
            continue

        # Vários imports conflitantes
        if len(imports) > 1:
            for module, _, lineno in imports:
                issues.append(VerifyIssue(
                    file=file_path,
                    line=lineno,
                    kind="MULTIPLE_IMPORTS",
                    detail=f"Import múltiplo de {function_name} ({module})"
                ))
            continue

        module, _, lineno = imports[0]

        # Import errado
        if module != expected_module:
            issues.append(VerifyIssue(
                file=file_path,
                line=lineno,
                kind="WRONG_IMPORT",
                detail=f"Importando de {module}, esperado {expected_module}"
            ))
            continue

        # OK
        issues.append(VerifyIssue(
            file=file_path,
            line=lineno,
            kind="OK",
            detail="Import correto"
        ))

    return VerifyResult(
        root=root,
        function_name=function_name,
        expected_import=expected_import,
        issues=issues
    )
    

def fix_imports(file_path: Path, target: str, expected_import: str):
    """
    Corrige imports de uma função dentro de um arquivo.
    """
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    new_lines = []
    has_correct_import = False
    has_any_import = False

    for line in lines:
        stripped = line.strip()

        # Detecta import da função
        if stripped.startswith("from ") and f"import {target}" in stripped:
            has_any_import = True

            if stripped == expected_import:
                has_correct_import = True
                new_lines.append(line)
            else:
                # Corrige import errado
                new_lines.append(expected_import)
        else:
            new_lines.append(line)

    # Se usa a função mas não tem import correto → inserir
    file_content = "\n".join(lines)
    uses_function = target in file_content

    if uses_function and not has_correct_import:
        insert_index = find_import_insertion_point(new_lines)
        new_lines.insert(insert_index, expected_import)

    file_path.write_text("\n".join(new_lines), encoding="utf-8")


def find_import_insertion_point(lines):
    """
    Encontra onde inserir imports (após bloco de imports).
    """
    last_import = -1

    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            last_import = i

    return last_import + 1


def verify_and_fix(root: Path, target: str, source_module: str, apply_fix=False):
    """
    Verifica e opcionalmente corrige imports.
    """
    expected_import = f"from {source_module} import {target}"

    ok = 0
    missing = 0
    wrong = 0

    for file in root.rglob("*.py"):
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if target not in content:
            continue

        lines = content.splitlines()

        has_correct = False
        has_import = False

        for line in lines:
            if f"import {target}" in line:
                has_import = True
                if expected_import in line:
                    has_correct = True

        if has_correct:
            ok += 1
            print(f"[OK] {file}")
        elif has_import:
            wrong += 1
            print(f"[WRONG] {file}")

            if apply_fix:
                fix_imports(file, target, expected_import)
                print(f"  [FIXED]")
        else:
            missing += 1
            print(f"[MISS] {file}")

            if apply_fix:
                fix_imports(file, target, expected_import)
                print(f"  [FIXED]")

    print("\n[RESUMO]")
    print(f"  OK: {ok}")
    print(f"  MISSING_IMPORT: {missing}")
    print(f"  WRONG_IMPORT: {wrong}")