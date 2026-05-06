# doxoade/doxoade/commands/check_systems/check_io.py
"""Especialista de I/O e Ancoragem (PASC 8.13)."""
import os
import json
from pathlib import Path
from typing import List, Dict
from doxoade.tools.filesystem import _find_project_root

class CheckIO:

    def __init__(self, target_path: str):
        self.target_abs = os.path.abspath(target_path)
        self.project_root = _find_project_root(self.target_abs)
        self.cache_dir = Path(self.project_root) / '.doxoade_cache'
        self.cache_file = self.cache_dir / 'check_cache.json'

    def resolve_files(self, target_files: List[str]=None) -> List[str]:
        if target_files:
            return [os.path.abspath(f) for f in target_files]
        if os.path.isfile(self.target_abs):
            return [self.target_abs]
        from doxoade.dnm import DNM
        return DNM(self.target_abs).scan(extensions=['py', 'c', 'cpp', 'h', 'hpp'])

    def load_cache(self) -> dict:
        """Carrega o banco de dados de escaneamentos anteriores."""
        if not self.cache_file.exists():
            return {}
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def save_cache(self, data: dict):
        """Persiste os resultados para o próximo check."""
        self.cache_dir.mkdir(exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def get_file_metadata(self, fp: str) -> tuple:
        try:
            st = os.stat(fp)
            return (st.st_mtime, st.st_size)
        except Exception:
            return (0, 0)
