# -*- coding: utf-8 -*-
# doxoade/commands/security_utils.py
import os
import sys
import shutil
from functools import lru_cache

SEVERITY_MAP = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

@lru_cache(maxsize=1) # Cache único para o path da ferramenta
def get_tool_path(tool_name: str) -> str:
    if not tool_name: return None
    exe = tool_name + ('.exe' if os.name == 'nt' else '')
    path_exe = shutil.which(tool_name)
    if path_exe: return path_exe
    search_dirs = [
        os.path.join(sys.prefix, 'Scripts' if os.name == 'nt' else 'bin'),
        os.path.join(os.getcwd(), 'venv', 'Scripts' if os.name == 'nt' else 'bin')
    ]
    for d in search_dirs:
        p = os.path.join(d, exe)
        if os.path.exists(p): return p
    return None

def batch_list(items: list, size: int):
    """PASC-6.4: Agrupamento para reduzir overhead de subprocessos."""
    for i in range(0, len(items), size):
        yield items[i : i + size]

def get_essential_ignores():
    # Adicionado .doxoade e .pytest_cache para blindagem total
    return {'.doxoade', '.git', 'venv', '.venv', '__pycache__', 'build', 'dist', 'docs', 'tests', '.pytest_cache'}

def is_path_ignored(filepath: str, ignore_list: set) -> bool:
    """Otimizado com sets para performance industrial."""
    if not filepath: return False
    norm_path = os.path.normpath(filepath).replace('\\', '/')
    path_parts = set(norm_path.split('/'))
    return not path_parts.isdisjoint(ignore_list)

def has_project_config(target_path: str) -> bool:
    configs = ['pyproject.toml', '.doxoade.toml', 'doxoade.toml']
    return any(os.path.exists(os.path.join(target_path, c)) for c in configs)