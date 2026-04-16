# doxoade/doxoade/commands/refactor_systems/refactor_rename.py
from __future__ import annotations
import os
import re
from pathlib import Path
IMPORT_RE = re.compile('^\\s*(from\\s+([\\w\\.]+)\\s+import|import\\s+([\\w\\.]+))')

def module_to_path(root: Path, module: str) -> Path:
    return root / Path(module.replace('.', '/') + '.py')

def replace_imports_in_file(file_path: Path, old: str, new: str) -> tuple[int, str]:
    """
    Substitui imports em um arquivo.
    Retorna: (qtd_substituições, novo_conteúdo)
    """
    try:
        text = file_path.read_text(encoding='utf-8')
    except Exception:
        return (0, '')
    count = 0
    pattern_from = re.compile(f'\\bfrom\\s+{re.escape(old)}\\b')
    text, c1 = pattern_from.subn(f'from {new}', text)
    pattern_import = re.compile(f'\\bimport\\s+{re.escape(old)}\\b')
    text, c2 = pattern_import.subn(f'import {new}', text)
    count = c1 + c2
    return (count, text)

def rename_module(root: Path, old_module: str, new_module: str, apply: bool=False):
    old_path = module_to_path(root, old_module)
    new_path = module_to_path(root, new_module)
    print(f'[RENAME] root: {root}')
    print(f'[RENAME] módulo antigo: {old_module}')
    print(f'[RENAME] módulo novo:   {new_module}')
    if not old_path.exists():
        print(f'[ERRO] arquivo não encontrado: {old_path}')
        return
    print(f'[FILE] {old_path} -> {new_path}')
    total_changes = 0
    files_changed = 0
    for py in root.rglob('*.py'):
        changes, new_text = replace_imports_in_file(py, old_module, new_module)
        if changes > 0:
            files_changed += 1
            total_changes += changes
            print(f'[UPDATE] {py} ({changes} mudanças)')
            if apply:
                py.write_text(new_text, encoding='utf-8')
    if apply:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        os.rename(old_path, new_path)
        print(f'[MOVE] arquivo renomeado')
    print('\n[RESUMO]')
    print(f'  arquivos alterados: {files_changed}')
    print(f'  imports atualizados: {total_changes}')
    print(f'  aplicado: {apply}')