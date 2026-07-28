# doxoade/doxoade/commands/refactor_systems/refactor_rename.py
from __future__ import annotations
import os
import re
from pathlib import Path
IMPORT_RE = re.compile('^\\s*(from\\s+([\\w\\.]+)\\s+import|import\\s+([\\w\\.]+))')

def module_to_path(root: Path, module: str) -> Path:
    return root / Path(module.replace('.', '/') + '.py')

def replace_imports_in_file(file_path: Path, old: str, new: str, root: Path = None) -> tuple[int, str]:
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
    
    # --- INJEÇÃO: LÓGICA DE IMPORTS RELATIVOS ---
    if root is not None:
        try:
            rel_path = file_path.relative_to(root)
            py_module = '.'.join(rel_path.with_suffix('').parts)
            old_rel = get_relative_import(py_module, old)
            new_rel = get_relative_import(py_module, new)
            if old_rel != new_rel and old_rel.startswith('.'):
                pattern_rel_from = re.compile(rf'^(\s*from\s+){re.escape(old_rel)}(\s+import)', re.MULTILINE)
                text, c3 = pattern_rel_from.subn(rf'\1{new_rel}\2', text)
                count += c3
        except ValueError:
            pass
    # ----------------------------------------------

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
#        changes, new_text = replace_imports_in_file(py, old_module, new_module)
        changes, new_text = replace_imports_in_file(py, old_module, new_module, root)
        if changes > 0:
            files_changed += 1
            total_changes += changes
            print(f'[UPDATE] {py} ({changes} mudanças)')
            if apply:
                py.write_text(new_text, encoding='utf-8')
    if apply:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        os.rename(old_path, new_path)
        print('[MOVE] arquivo renomeado')
    print('\n[RESUMO]')
    print(f'  arquivos alterados: {files_changed}')
    print(f'  imports atualizados: {total_changes}')
    print(f'  aplicado: {apply}')
    
def get_relative_import(from_module: str, to_module: str) -> str:
    """Calcula o import relativo de 'to_module' a partir de 'from_module'."""
    from_parts = from_module.split('.')
    to_parts = to_module.split('.')
    
    common_length = 0
    for f, t in zip(from_parts, to_parts):
        if f == t:
            common_length += 1
        else:
            break
            
    if common_length == 0:
        return to_module
        
    from_pkg_parts = from_parts[:-1]
    up_levels = len(from_pkg_parts) - common_length
    down_parts = to_parts[common_length:]
    
    dots = '.' * (up_levels + 1)
    if down_parts:
        return dots + '.'.join(down_parts)
    else:
        return dots[:-1] if up_levels > 0 else '.'