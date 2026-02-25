# -*- coding: utf-8 -*-
# doxoade/commands/impact_systems/impact_utils.py
import os
import json
# [DOX-UNUSED] from tools.doxcolors import Fore
from pathlib import Path
def get_file_metadata(fp: str) -> tuple:
    """Retorna (mtime, size) para validação de cache."""
    try:
        st = os.stat(fp)
        return int(st.st_mtime), st.st_size
    except Exception: return 0, 0
def load_impact_cache(root_path: str) -> dict:
    """Carrega o índice persistido (PASC-8.3)."""
    cache_file = Path(root_path) / ".doxoade_cache" / "impact_index.json"
    if not cache_file.exists(): return {}
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception: return {}
def save_impact_cache(root_path: str, data: dict):
    """Persiste o índice no disco."""
    cache_dir = Path(root_path) / ".doxoade_cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "impact_index.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        import sys as dox_exc_sys
        _, exc_obj, exc_tb = dox_exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[0m \033[1m Filename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \033[0m")
    
def path_to_module_name(file_path: str, search_path: str) -> str:
    """
    Converte um caminho de arquivo em nome de módulo (PASC-8.15).
    Ex: 'doxoade/tools/git.py' -> 'doxoade.tools.git'
    """
    try:
        rel_path = os.path.relpath(file_path, search_path)
        base = os.path.splitext(rel_path)[0]
        return base.replace(os.sep, '.').replace('/', '.')
    except Exception:
        return "unknown"
def resolve_relative_import(module: str, level: int, current_module: str) -> str:
    """Resolve a hierarquia de imports como 'from ..tools import x'."""
    if level == 0: return module
    
    parts = current_module.split('.')
    # Remove 'level' partes do final para subir na árvore
    target_parts = parts[:-level]
    if module:
        target_parts.append(module)
    return ".".join(target_parts)
def get_coupling_status(fan_out: int, fan_in: int):
    """Calcula métrica de acoplamento (Atena Architecture)."""
    from doxoade.tools.doxcolors import Fore
    total = fan_out + fan_in
    if total == 0: return 0.0, (Fore.GREEN, "Independente")
    
    instability = fan_out / total
    if instability > 0.7: return instability, (Fore.RED, "Frágil/Dependente")
    if instability < 0.3: return instability, (Fore.CYAN, "Sólido/Central")
    return instability, (Fore.YELLOW, "Estável")