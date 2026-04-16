# doxoade/doxoade/commands/refactor_systems/refactor_rename_ast.py
from __future__ import annotations
import ast
from dataclasses import dataclass, field
from pathlib import Path
from .refactor_utils import iter_python_files, read_text_safe

@dataclass(frozen=True)
class ImportRewrite:
    file: Path
    lineno: int
    end_lineno: int
    original: str
    rewritten: str

@dataclass
class RenameResult:
    root: Path
    old_module: str
    new_module: str
    source_file: Path
    dest_file: Path
    apply: bool
    changed_files: list[Path] = field(default_factory=list)
    rewrites: list[ImportRewrite] = field(default_factory=list)
    moved_file: bool = False

def _module_to_path(root: Path, module: str) -> Path:
    return root / Path(module.replace('.', '/') + '.py')

def _rewrite_module_name(module_name: str, old_module: str, new_module: str) -> str:
    if module_name == old_module:
        return new_module
    if module_name.startswith(old_module + '.'):
        return new_module + module_name[len(old_module):]
    return module_name

def _alias_text(alias: ast.alias) -> str:
    return f'{alias.name} as {alias.asname}' if alias.asname else alias.name

def _indent_of(line: str) -> str:
    return line[:len(line) - len(line.lstrip(' \t'))]

def _build_import_stmt(node: ast.AST, old_module: str, new_module: str) -> str | None:
    if isinstance(node, ast.Import):
        parts = []
        changed = False
        for alias in node.names:
            new_name = _rewrite_module_name(alias.name, old_module, new_module)
            changed = changed or new_name != alias.name
            parts.append(_alias_text(ast.alias(name=new_name, asname=alias.asname)))
        if not changed:
            return None
        return 'import ' + ', '.join(parts)
    if isinstance(node, ast.ImportFrom):
        if node.module is None:
            return None
        new_mod = _rewrite_module_name(node.module, old_module, new_module)
        if new_mod == node.module:
            return None
        prefix = '.' * node.level
        module_part = f'{prefix}{new_mod}' if new_mod else prefix
        parts = ', '.join((_alias_text(alias) for alias in node.names))
        return f'from {module_part} import {parts}'
    return None

def _collect_import_rewrites(source_text: str, file_path: Path, old_module: str, new_module: str) -> list[ImportRewrite]:
    try:
        tree = ast.parse(source_text, filename=str(file_path))
    except SyntaxError:
        return []
    except Exception:
        return []
    lines = source_text.splitlines()
    edits: list[ImportRewrite] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        replacement = _build_import_stmt(node, old_module, new_module)
        if replacement is None:
            continue
        start = getattr(node, 'lineno', None)
        end = getattr(node, 'end_lineno', None)
        if start is None:
            continue
        if end is None:
            end = start
        original = '\n'.join(lines[start - 1:end])
        indent = _indent_of(lines[start - 1]) if 0 <= start - 1 < len(lines) else ''
        rewritten = f'{indent}{replacement}'
        edits.append(ImportRewrite(file=file_path, lineno=int(start), end_lineno=int(end), original=original, rewritten=rewritten))
    return edits

def _apply_rewrites(source_text: str, rewrites: list[ImportRewrite]) -> str:
    if not rewrites:
        return source_text
    lines = source_text.splitlines()
    for rw in sorted(rewrites, key=lambda x: (x.lineno, x.end_lineno), reverse=True):
        start = max(rw.lineno - 1, 0)
        end = max(rw.end_lineno, start + 1)
        lines[start:end] = [rw.rewritten]
    return '\n'.join(lines) + '\n'

def rename_module_ast(root: Path, old_module: str, new_module: str, apply: bool=False, overwrite: bool=False) -> RenameResult:
    root = root.resolve()
    old_module = old_module.strip()
    new_module = new_module.strip()
    source_file = _module_to_path(root, old_module)
    dest_file = _module_to_path(root, new_module)
    if not source_file.exists():
        raise RuntimeError(f'Arquivo do módulo antigo não encontrado: {source_file}')
    if dest_file.exists() and (not overwrite) and (source_file != dest_file):
        raise RuntimeError(f'Arquivo de destino já existe: {dest_file}')
    result = RenameResult(root=root, old_module=old_module, new_module=new_module, source_file=source_file, dest_file=dest_file, apply=apply)
    pending_file_text: dict[Path, str] = {}
    for py_file in iter_python_files(root):
        try:
            source_text = read_text_safe(py_file)
        except Exception:
            continue
        rewrites = _collect_import_rewrites(source_text, py_file, old_module, new_module)
        if not rewrites:
            continue
        result.changed_files.append(py_file)
        result.rewrites.extend(rewrites)
        pending_file_text[py_file] = _apply_rewrites(source_text, rewrites)
    if apply:
        for py_file, new_text in pending_file_text.items():
            py_file.write_text(new_text, encoding='utf-8')
        if source_file != dest_file:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if dest_file.exists() and overwrite:
                dest_file.unlink()
            source_file.replace(dest_file)
        result.moved_file = True
    return result