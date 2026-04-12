# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_assembler.py
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from .refactor_utils import FunctionHit, collect_function_defs, read_text_safe


@dataclass(frozen=True)
class MovePlan:
    project_root: Path
    source_file: Path
    dest_file: Path
    function_name: str
    source_module: str
    dest_module: str
    function_hit: FunctionHit


@dataclass(frozen=True)
class MoveResult:
    plan: MovePlan
    created_dest: bool
    source_updated: bool
    dest_valid: bool
    source_valid: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


def _module_name(project_root: Path, file_path: Path) -> str:
    project_root = project_root.resolve()
    file_path = file_path.resolve()
    rel = file_path.relative_to(project_root)
    return ".".join(rel.with_suffix("").parts)


def _function_span(node: ast.AST) -> tuple[int, int]:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)

    decorators = getattr(node, "decorator_list", [])
    if decorators:
        start = min([start] + [getattr(dec, "lineno", start) for dec in decorators])

    return int(start), int(end)


def _find_function_node(tree: ast.AST, function_name: str) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return node
    return None


def _extract_block(lines: list[str], start_line: int, end_line: int) -> str:
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    return "\n".join(lines[start_idx:end_idx]).rstrip() + "\n"


def _remove_block(lines: list[str], start_line: int, end_line: int) -> str:
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    
    # Exclui as linhas exatas da função (incluindo decorators)
    del lines[start_idx:end_idx]
    
    return "\n".join(lines) + ("\n" if lines and lines[-1] != "" else "")


def _get_top_level_imports(source_text: str) -> str:
    """Extrai os imports do topo do arquivo origem para inicializar o destino."""
    try:
        tree = ast.parse(source_text)
    except Exception:
        return ""

    import_lines = []
    lines = source_text.splitlines()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = getattr(node, "lineno", 1) - 1
            end = getattr(node, "end_lineno", start + 1)
            import_lines.extend(lines[start:end])
    
    if import_lines:
        return "\n".join(import_lines) + "\n\n"
    return ""


def prepare_move_plan(root: Path, source: Path, function_name: str, dest: Path) -> MovePlan | None:
    source = source.resolve()
    dest = dest.resolve()
    root = root.resolve()

    hits = collect_function_defs(source)
    target_hits = [h for h in hits if h.name == function_name]

    if not target_hits:
        return None

    best_hit = target_hits[0]
    for h in target_hits:
        if h.qualname == function_name:
            best_hit = h
            break

    return MovePlan(
        project_root=root,
        source_file=source,
        dest_file=dest,
        function_name=function_name,
        source_module=_module_name(root, source),
        dest_module=_module_name(root, dest),
        function_hit=best_hit
    )


def move_function(plan: MovePlan) -> MoveResult:
    source_text = read_text_safe(plan.source_file)
    try:
        source_tree = ast.parse(source_text)
    except Exception as e:
        return MoveResult(plan, False, False, False, False, notes=(f"Erro parse origem: {e}",))

    func_node = _find_function_node(source_tree, plan.function_name)
    if not func_node:
        return MoveResult(plan, False, False, False, False, notes=("Função não encontrada na AST.",))

    start_line, end_line = _function_span(func_node)
    source_lines = source_text.splitlines()

    # 1. Extrair código da origem
    func_code = _extract_block(source_lines, start_line, end_line)

    # 2. Remover da origem
    new_source_text = _remove_block(source_lines.copy(), start_line, end_line)
    
    source_valid = True
    try:
        ast.parse(new_source_text)
    except Exception:
        source_valid = False

    if not source_valid:
        return MoveResult(plan, False, False, False, False, notes=("A remoção quebraria a sintaxe da origem.",))

    # 3. Inserir no destino
    created_dest = False
    dest_text = ""
    if plan.dest_file.exists():
        dest_text = read_text_safe(plan.dest_file)
    else:
        created_dest = True
        plan.dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_text = "from __future__ import annotations\n\n" + _get_top_level_imports(source_text)

    try:
        dest_tree = ast.parse(dest_text)
        if _find_function_node(dest_tree, plan.function_name):
            return MoveResult(plan, False, False, False, True, notes=("A função já existe no destino.",))
    except Exception:
        pass

    if dest_text and not dest_text.endswith("\n\n"):
        dest_text += "\n\n" if not dest_text.endswith("\n") else "\n"
            
    new_dest_text = dest_text + func_code + "\n"

    dest_valid = True
    try:
        ast.parse(new_dest_text)
    except Exception:
        dest_valid = False

    if not dest_valid:
        return MoveResult(plan, created_dest, False, False, True, notes=("Inserção quebraria a sintaxe do destino.",))

    # 4. Escrever em disco
    plan.source_file.write_text(new_source_text, encoding="utf-8")
    plan.dest_file.write_text(new_dest_text, encoding="utf-8")

    return MoveResult(
        plan=plan,
        created_dest=created_dest,
        source_updated=True,
        dest_valid=True,
        source_valid=True,
        notes=("Função isolada e movida com sucesso.",)
    )