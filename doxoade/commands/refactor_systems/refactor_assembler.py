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


def _module_name_from_file(project_root: Path, file_path: Path) -> str:
    return _module_name(project_root, file_path)


def _function_span(node: ast.AST) -> tuple[int, int]:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)

    decorators = getattr(node, "decorator_list", []) or []
    if decorators:
        start = min([start] + [getattr(dec, "lineno", start) for dec in decorators])

    if start is None:
        start = 1
    if end is None:
        end = start

    return int(start), int(end)


def _find_function_node(tree: ast.AST, function_name: str, function_line: int | None = None) -> ast.AST | None:
    class Finder(ast.NodeVisitor):
        def __init__(self) -> None:
            self.match: ast.AST | None = None

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == function_name:
                if function_line is None or getattr(node, "lineno", None) == function_line:
                    self.match = node
                    return
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node.name == function_name:
                if function_line is None or getattr(node, "lineno", None) == function_line:
                    self.match = node
                    return
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if self.match is not None:
                return
            self.generic_visit(node)

    finder = Finder()
    finder.visit(tree)
    return finder.match


def _extract_block(lines: list[str], start_line: int, end_line: int) -> str:
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    return "\n".join(lines[start_idx:end_idx]).rstrip() + "\n"


def _remove_block(lines: list[str], start_line: int, end_line: int) -> str:
    start_idx = max(start_line - 1, 0)
    end_idx = min(end_line, len(lines))
    new_lines = lines[:start_idx] + lines[end_idx:]

    while new_lines and not new_lines[0].strip():
        new_lines.pop(0)
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    return "\n".join(new_lines) + ("\n" if new_lines else "")


def _top_level_import_lines(tree: ast.AST, source_lines: list[str]) -> list[str]:
    imports: list[str] = []

    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start, end = _function_span(node)
            imports.extend(source_lines[start - 1:end])

    return imports


def _future_import_lines(tree: ast.AST, source_lines: list[str]) -> list[str]:
    imports: list[str] = []

    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            start, end = _function_span(node)
            imports.extend(source_lines[start - 1:end])

    return imports


def _insert_import_into_source(source_text: str, import_line: str) -> str:
    if import_line in source_text:
        return source_text

    lines = source_text.splitlines()

    if not lines:
        return import_line + "\n"

    insert_at = 0

    try:
        tree = ast.parse(source_text)
    except Exception:
        return import_line + "\n" + source_text

    body = getattr(tree, "body", [])
    if not body:
        return import_line + "\n" + source_text

    idx = 0

    if body and isinstance(body[0], ast.Expr):
        value = getattr(body[0], "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            insert_at = getattr(body[0], "end_lineno", 1)
            idx = 1

    while idx < len(body):
        node = body[idx]
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_at = max(insert_at, getattr(node, "end_lineno", insert_at))
            idx += 1
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert_at = max(insert_at, getattr(node, "end_lineno", insert_at))
            idx += 1
            continue
        break

    if insert_at <= 0:
        return import_line + "\n" + source_text

    insert_idx = min(insert_at, len(lines))
    new_lines = lines[:insert_idx] + [import_line, ""] + lines[insert_idx:]
    return "\n".join(new_lines).rstrip() + "\n"


def _build_dest_text(
    source_text: str,
    function_block: str,
    top_imports: list[str],
    future_imports: list[str],
) -> str:
    parts: list[str] = ["from __future__ import annotations", ""]

    seen: set[str] = set()
    for line in future_imports + top_imports:
        stripped = line.rstrip()
        if not stripped or stripped in seen:
            continue
        parts.append(stripped)
        seen.add(stripped)

    if parts[-1] != "":
        parts.append("")

    parts.append(function_block.rstrip())
    parts.append("")
    return "\n".join(parts)


def _validate_python(path: Path) -> bool:
    try:
        ast.parse(read_text_safe(path), filename=str(path))
        return True
    except Exception:
        return False


def prepare_move_plan(project_root: Path, source_file: Path, function_name: str, dest_file: Path) -> MovePlan:
    project_root = project_root.resolve()
    source_file = source_file.resolve()
    dest_file = dest_file.resolve()
    function_name = function_name.strip()

    if not source_file.exists():
        raise RuntimeError(f"Arquivo de origem não existe: {source_file}")
    if not dest_file.parent.exists():
        raise RuntimeError(f"Pasta de destino não existe: {dest_file.parent}")

    hits = collect_function_defs(source_file)
    candidates = [hit for hit in hits if hit.name == function_name]

    if not candidates:
        raise RuntimeError(f"Função não encontrada no arquivo de origem: {function_name}")
    if len(candidates) > 1:
        lines = ", ".join(f"{hit.file}:{hit.line}" for hit in candidates)
        raise RuntimeError(f"Função ambígua em {source_file}: {function_name} -> {lines}")

    function_hit = candidates[0]

    source_module = _module_name_from_file(project_root, source_file)
    dest_module = _module_name_from_file(project_root, dest_file)

    return MovePlan(
        project_root=project_root,
        source_file=source_file,
        dest_file=dest_file,
        function_name=function_name,
        source_module=source_module,
        dest_module=dest_module,
        function_hit=function_hit,
    )

def _check_function_exists_in_file(dest_text: str, function_name: str) -> bool:
    """Retorna True se function_name já está definida no topo do arquivo."""
    try:
        tree = ast.parse(dest_text)
    except SyntaxError:
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
        and getattr(node, "col_offset", 0) == 0
        for node in ast.walk(tree)
    )


def _merge_function_into_existing(
    dest_text: str,
    function_name: str,
    function_block: str,
    import_lines: list[str],
) -> tuple[str, list[str]]:
    """
    Insere function_block num arquivo existente.

    Retorna (novo_texto, notas).
    Levanta ValueError se a função já estiver definida no destino.
    """
    if _check_function_exists_in_file(dest_text, function_name):
        raise ValueError(
            f"Função '{function_name}' já está definida no arquivo de destino. "
            "Use --overwrite para substituir o arquivo inteiro."
        )

    notes: list[str] = []

    # Mescla imports ausentes
    merged = dest_text
    for imp in import_lines:
        imp = imp.strip()
        if imp and imp not in merged:
            merged = _insert_import_into_source(merged, imp)
            notes.append(f"import adicionado: {imp}")

    # Appenda a função com dois newlines de espaçamento
    merged = merged.rstrip("\n") + "\n\n\n" + function_block.rstrip("\n") + "\n"

    return merged, notes

def move_function(plan: MovePlan, overwrite: bool = False) -> MoveResult:
    source_text = read_text_safe(plan.source_file)
    if not source_text:
        raise RuntimeError(f"Não foi possível ler a origem: {plan.source_file}")

    tree = ast.parse(source_text, filename=str(plan.source_file))
    node = _find_function_node(tree, plan.function_name, plan.function_hit.line)
    if node is None:
        raise RuntimeError(f"Não foi possível localizar a função no AST: {plan.function_name}")

    start_line, end_line = _function_span(node)
    source_lines = source_text.splitlines()

    function_block = _extract_block(source_lines, start_line, end_line)
    remaining_source = _remove_block(source_lines, start_line, end_line)

    top_imports = _top_level_import_lines(tree, source_lines)
    future_imports = _future_import_lines(tree, source_lines)

    dest_imported = f"from {plan.source_module} import {plan.function_name}"
    updated_source = _insert_import_into_source(remaining_source, dest_imported)
    filtered_imports = _filter_imports_for_function(function_block, top_imports)
    
    created_dest = False
    if plan.dest_file.exists() and not overwrite:
        dest_text = read_text_safe(plan.dest_file)
        try:
            new_dest_text, extra_notes = _merge_function_into_existing(
                dest_text,
                plan.function_name,
                function_block,
                filtered_imports,     # ← só o que a função realmente usa
            )
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        # Grava primeiro, valida depois (igual ao caminho do overwrite)
        dest_backup = dest_text
        plan.dest_file.write_text(new_dest_text, encoding="utf-8")
        if not _validate_python(plan.dest_file):          # ← recebe Path, não str
            plan.dest_file.write_text(dest_backup, encoding="utf-8")
            raise RuntimeError("Falha de validação sintática no arquivo de destino após merge.")

        return MoveResult(
            plan=plan,
            created_dest=False,
            source_updated=True,
            dest_valid=True,
            source_valid=True,
            notes=tuple(
                [f"função inserida em arquivo existente: {plan.dest_file}"] + extra_notes
            ),
        )

    if not plan.dest_file.exists():
        created_dest = True

    dest_text = _build_dest_text(source_text, function_block, top_imports, future_imports)

    source_backup = source_text
    dest_backup = plan.dest_file.read_text(encoding="utf-8") if plan.dest_file.exists() else None

    try:
        plan.dest_file.write_text(dest_text, encoding="utf-8")
        plan.source_file.write_text(updated_source, encoding="utf-8")

        dest_valid = _validate_python(plan.dest_file)
        source_valid = _validate_python(plan.source_file)

        if not dest_valid or not source_valid:
            raise RuntimeError("Falha de validação sintática após a movimentação.")

    except Exception:
        plan.source_file.write_text(source_backup, encoding="utf-8")
        if dest_backup is None:
            try:
                plan.dest_file.unlink()
            except Exception:
                pass
        else:
            plan.dest_file.write_text(dest_backup, encoding="utf-8")
        raise

    return MoveResult(
        plan=plan,
        created_dest=created_dest,
        source_updated=True,
        dest_valid=True,
        source_valid=True,
        notes=(
            f"Função movida para {plan.dest_file}",
            f"Import adicionada em {plan.source_file}: {dest_imported}",
        ),
    )
    
def _filter_imports_for_function(function_block: str, import_lines: list[str]) -> list[str]:
    """Retorna apenas os imports cujos nomes aparecem no corpo da função."""
    needed: list[str] = []
    for line in import_lines:
        line = line.strip()
        if not line:
            continue
        try:
            tree = ast.parse(line)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if any(
                    alias.asname in function_block if alias.asname else alias.name in function_block
                    for alias in node.names
                ):
                    needed.append(line)
                    break
            elif isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] in function_block for alias in node.names):
                    needed.append(line)
                    break
    return needed