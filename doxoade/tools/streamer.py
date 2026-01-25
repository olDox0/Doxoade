# -*- coding: utf-8 -*-
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

    def get_lines(self, file_path):
        """Retorna as linhas do arquivo, usando cache se disponível."""
        if file_path in self._cache:
            self.reads_saved += 1
            return self._cache[file_path]
        
        abs_path = os.path.normpath(file_path).replace('\\', '/')
        
        if abs_path in self._cache:
            return self._cache[abs_path]
        
#        if abs_path in self._cache:
#            self.reads_saved += 1
#            return self._cache[abs_path]
        
        # [FIX MPoT-7] Desempacotamento correto para o trio (cpu, ram, disk)
        _, ram_usage, _ = governor.get_system_health()
        
        try:
            # PASC-6.3: Sempre UTF-8
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # Só armazena em cache se a RAM estiver saudável
            if ram_usage < 80.0:
                self._cache[abs_path] = lines
            return lines
        except Exception:
            return []

    def clear(self):
        """Limpa o cache após o fim de um comando (Flush)."""
        self._cache.clear()

# Singleton UFS
ufs = FileStreamer()