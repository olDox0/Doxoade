# -*- coding: utf-8 -*-
# doxoade/tools/streamer.py
"""
Doxoade Unified File Streamer (UFS) - v1.0.
Evita múltiplas leituras de disco (Hot Line Fix).
Compliance: PASC-6.4, MPoT-3.
"""
import os
# [DOX-UNUSED] import sys
from .governor import governor

class FileStreamer:
    """UFS v1.1 - Gerenciador de Fluxo de Dados RAM-First."""
    def __init__(self):
        self._cache = {} # {path: lines_list}
        self.reads_saved = 0

    def _canonical(self, path):
        """Padroniza o path para evitar falhas de cache no Windows."""
        return os.path.abspath(path).replace('\\', '/').lower()

    def get_lines(self, file_path):
        """Retorna lista de strings. Garante integridade do tipo de retorno."""
        abs_path = os.path.abspath(file_path).replace('\\', '/').lower()
        
        if abs_path in self._cache:
            self.reads_saved += 1
            return self._cache[abs_path]
        
        try:
            # PASC 6.3: Normalização UTF-8 obrigatória
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Só armazena se o Governor (Almoxarife) permitir
            if governor.enabled: # Verifica se há RAM disponível
                self._cache[abs_path] = lines
            return lines
        except Exception:
            return [] # Fail-safe: retorna lista vazia para não quebrar o loop 'for'

    def clear(self):
        self._cache.clear()

    def get_raw_content(self, file_path):
        """
        Retorna bytes brutos para o Vulcan Scan (PASC-6.4).
        Evita o overhead de decodificação UTF-8 se o Vulcan for usado.
        """
        key = self._canonical(file_path) + ":raw"
        if key in self._cache:
            return self._cache[key]
            
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                # Armazena se a RAM permitir (Governança via Governor)
                _, ram_usage, _ = governor.get_system_health()
                if ram_usage < 85.0:
                    self._cache[key] = data
                return data
        except Exception as e:
            print(f"\033[0;33m get_raw_content - Exception: {e}")
            return b""

# Singleton UFS
ufs = FileStreamer()