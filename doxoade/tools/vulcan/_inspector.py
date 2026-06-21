# -*- coding: utf-8 -*-
# engine/tools/vulcan/_inspector.py
"""
ORN — Vulcan Inspector Engine (Anúbis)
Realiza a varredura estática de arquivos .pyx e .c para medir a fricção C-API.

PASC 1.3: Arquivo focado em análise, mantendo o limite de peso.
OSL-18: Dependência exclusiva da stdlib (re, os, math).
"""

from __future__ import annotations
import re
import os
from typing import Dict, Any

# Símbolos da C-API do Python que geram "Calor" (Fricção)
# Se estes caras aparecem muito no seu .c, a tradução foi pesada.
HOT_SYMBOLS = {
    "PyObject_GetAttr": 10,     # Muito caro (lookup dinâmico)
    "PyObject_GetItem": 12,     # Caro (acesso a dict/list sem tipagem)
    "PyNumber_Add": 8,          # Adição genérica (lento)
    "Py_INCREF": 2,             # Gestão de referência (overhead de memória)
    "Py_DECREF": 2,
    "PyImport_ImportModule": 20, # Crítico: importação em tempo de execução
    "PyEval_EvalCode": 50,      # Explosivo: código rodando via interpretador
    "PyErr_Occurred": 5,        # Checagem de erro constante
}

class VulcanInspector:
    """Auditor de qualidade de tradução Ignite/Cython."""

    def __init__(self, path: str):
        self.path = path
        self.stats = {"lines": 0, "hot_calls": 0, "score": 0, "symbols_found": {}}

    def inspect_c_lang(self) -> Dict[str, Any]:
        """Analisa o arquivo .c gerado buscando 'Hot Symbols'."""
        if not os.path.exists(self.path):
            return {"error": f"Arquivo C não encontrado: {self.path}"}

        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            self.stats["lines"] = len(content.splitlines())
            
            for sym, weight in HOT_SYMBOLS.items():
                count = len(re.findall(re.escape(sym), content))
                if count > 0:
                    self.stats["symbols_found"][sym] = count
                    self.stats["hot_calls"] += count
                    self.stats["score"] += (count * weight)

        return self.stats

    def inspect_cython(self) -> Dict[str, Any]:
        """Analisa o código .pyx buscando falta de tipagem estática."""
        if not os.path.exists(self.path):
            return {"error": f"Arquivo Cython não encontrado: {self.path}"}

        analysis = {"untyped_vars": 0, "untyped_args": 0, "loops": 0}
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                # Caça loops que podem ser gargalos
                if re.search(r"\s+(for|while)\s+", line):
                    analysis["loops"] += 1
                # Caça variáveis sem 'cdef' ou tipos explicitos
                if re.search(r"^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*", line):
                    if "cdef" not in line:
                        analysis["untyped_vars"] += 1
        return analysis

def get_line_expansion_ratio(pyx_path: str, c_path: str) -> float:
    """Mede o Coeficiente de Expansão (PASC 6.4)."""
    try:
        with open(pyx_path, "r") as f: pyx_l = len(f.readlines())
        with open(c_path, "r") as f: c_l = len(f.readlines())
        return round(c_l / max(1, pyx_l), 2)
    except Exception:
        return 0.0