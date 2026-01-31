# -*- coding: utf-8 -*-
# doxoade/tools/streamer.py
"""
Doxoade Unified File Streamer (UFS) - v1.0.
Evita múltiplas leituras de disco (Hot Line Fix).
Compliance: PASC-6.4, MPoT-3.
"""
import os
from .governor import governor

class FileStreamer:
    """Cache efêmero de arquivos para o ciclo de auditoria."""
    
    def __init__(self):
        self._cache = {} # {path: lines_list}
        self.reads_saved = 0

    def _canonical(self, path):
        """Padroniza o path para evitar falhas de cache no Windows."""
        return os.path.abspath(path).replace('\\', '/').lower()

    def get_lines(self, file_path):
        key = self._canonical(file_path)
        if key in self._cache:
            self.reads_saved += 1
            return self._cache[key]
        
        _, ram_usage, _ = governor.get_system_health()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            if ram_usage < 85.0:
                self._cache[key] = lines
            return lines
        except: return []

    def clear(self):
        self._cache.clear()

# Singleton UFS
ufs = FileStreamer()