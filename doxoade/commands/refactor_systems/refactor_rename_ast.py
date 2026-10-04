# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_rename_ast.py
from __future__ import annotations
import ast
import click

from dataclasses import dataclass, field
from pathlib import Path

from .refactor_cache import RefactorDependencyCache
from .refactor_utils import iter_python_files, read_text_safe, write_text_safe
from .refactor_preview import print_snippet_diff

@dataclass(frozen=True)
class ImportRewrite:
    file: Path
    lineno: int
    end_lineno: int
    original: str
    rewritten: str

@dataclass
class BatchRenameResult:
    root: Path
    module_mapping: dict[str, str]  # {old_mod: new_mod}
    apply: bool
    changed_files: dict[Path, str] = field(default_factory=dict)
    rewrites_count: int = 0

def _module_to_path(root: Path, module: str) -> Path:
    return root / Path(module.replace('.', '/') + '.py')

def _rewrite_module_name(module_name: str, mapping: dict[str, str]) -> str:
    """Substitui o nome do módulo usando o mapeamento do lote."""
    if module_name in mapping:
        return mapping[module_name]
    for old_mod, new_mod in mapping.items():
        if module_name.startswith(old_mod + '.'):
            return new_mod + module_name[len(old_mod):]
    return module_name

def _alias_text(alias: ast.alias) -> str:
    return f'{alias.name} as {alias.asname}' if alias.asname else alias.name

def _indent_of(line: str) -> str:
    return line[:len(line) - len(line.lstrip(' \t'))]

def _build_batch_import_stmt(node: ast.AST, mapping: dict[str, str]) -> str | None:
    if isinstance(node, ast.Import):
        parts = []
        changed = False
        for alias in node.names:
            new_name = _rewrite_module_name(alias.name, mapping)
            changed = changed or (new_name != alias.name)
            parts.append(_alias_text(ast.alias(name=new_name, asname=alias.asname)))
        if not changed:
            return None
        return 'import ' + ', '.join(parts)

    if isinstance(node, ast.ImportFrom):
        if node.module is None:
            return None
        new_mod = _rewrite_module_name(node.module, mapping)
        if new_mod == node.module:
            return None
        prefix = '.' * node.level
        module_part = f'{prefix}{new_mod}' if new_mod else prefix
        parts = ', '.join((_alias_text(alias) for alias in node.names))
        return f'from {module_part} import {parts}'

    return None

def _apply_rewrites(source_text: str, rewrites: list[ImportRewrite]) -> str:
    if not rewrites:
        return source_text
    lines = source_text.splitlines()
    for rw in sorted(rewrites, key=lambda x: (x.lineno, x.end_lineno), reverse=True):
        start = max(rw.lineno - 1, 0)
        end = max(rw.end_lineno, start + 1)
        lines[start:end] = [rw.rewritten]
    return '\n'.join(lines) + '\n'

def rename_modules_batch(
    root: Path,
    mapping: dict[str, str],
    apply: bool = False,
    dry_run: bool = False
) -> BatchRenameResult:
    root = root.resolve()
    result = BatchRenameResult(root=root, module_mapping=mapping, apply=apply)

    # 1. Sincroniza o cache incremental em disco (~10ms)
    dep_cache = RefactorDependencyCache(root)
    dep_cache.sync()

    # 2. Descobre instantaneamente quais arquivos importam os módulos alvos
    target_files = dep_cache.find_affected_files(set(mapping.keys()))

    # 3. Processa SOMENTE os arquivos identificados (ex: 4 arquivos em vez de 300)
    for py_file in target_files:
        if not py_file.exists():
            continue
        source_text = read_text_safe(py_file)
        try:
            tree = ast.parse(source_text, filename=str(py_file))
        except Exception:
            continue

        lines = source_text.splitlines()
        edits: list[ImportRewrite] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            replacement = _build_batch_import_stmt(node, mapping)
            if replacement is None:
                continue

            start = getattr(node, 'lineno', None)
            end = getattr(node, 'end_lineno', start)
            if start is None:
                continue

            original = '\n'.join(lines[start - 1:end])
            indent = _indent_of(lines[start - 1]) if 0 <= start - 1 < len(lines) else ''
            rewritten = f'{indent}{replacement}'
            edits.append(ImportRewrite(file=py_file, lineno=int(start), end_lineno=int(end), original=original, rewritten=rewritten))

        if edits:
            result.changed_files[py_file] = _apply_rewrites(source_text, edits)
            result.rewrites_count += len(edits)

    # 2. Exibição de Diff unificada
    if dry_run or not apply:
        click.secho("\n🔍 [PREVIEW] Alterações de Importação Detectadas no Projeto:", fg='yellow', bold=True)
        if not result.changed_files:
            click.echo("Nenhuma alteração de importação necessária nos arquivos do projeto.")
        for py_file, new_text in result.changed_files.items():
            original_text = read_text_safe(py_file)
            orig_lines = original_text.splitlines(keepends=True)
            new_lines = new_text.splitlines(keepends=True)
            print_snippet_diff(py_file, orig_lines, new_lines, context=2)

    # 3. Aplicação Atômica
    if apply:
        # A. Atualiza imports de todos os arquivos afetados
        for py_file, new_text in result.changed_files.items():
            write_text_safe(py_file, new_text)

        # B. Move fisicamente os arquivos declarados no batch
        for old_mod, new_mod in mapping.items():
            src_f = _module_to_path(root, old_mod)
            dst_f = _module_to_path(root, new_mod)
            if src_f.exists() and src_f != dst_f:
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                if dst_f.exists():
                    dst_f.unlink()
                src_f.replace(dst_f)

    return result
