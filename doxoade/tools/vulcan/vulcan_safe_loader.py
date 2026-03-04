# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/vulcan_safe_loader.py
"""
SafeExtensionLoader — Carregador de 3 Camadas para Binários Vulcan.
====================================================================

Hierarquia de fallback (prioridade decrescente):

  Tier 1 — Binário Nativo (.pyd/.so)
      ExtensionFileLoader padrão. Máxima performance.
      Falha → Tier 2.

  Tier 2 — Python Otimizado (.py do opt_cache)
      Módulo pré-processado pelo LibOptimizer: sem docstrings, dead code
      eliminado, imports limpos, variáveis locais minificadas.
      Falha → Tier 3.

  Tier 3 — Python Puro (fonte original)
      Sem transformações. Comportamento idêntico ao carregamento normal.
      Falha → propaga exceção (erro real de import).

O SafeExtensionLoader é usado pelo VulcanMetaFinder (meta_finder.py) e
pelo VulcanBinaryFinder (runtime.py) como loader do ModuleSpec.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional


class SafeExtensionLoader(importlib.machinery.ExtensionFileLoader):
    """
    Loader seguro com fallback tri-nível para extensões Cython.

    Parâmetros:
        fullname     — nome completo do módulo (ex: ``click.utils``)
        path         — path do .pyd/.so
        py_fallback  — path do .py original (para Tier 2 e Tier 3)
    """

    def __init__(self, fullname: str, path: str, py_fallback: Optional[str] = None):
        super().__init__(fullname, path)
        self._py_fallback = py_fallback

    # ── Entry-point principal ────────────────────────────────────────────────

    def exec_module(self, module) -> None:
        """
        Executa o módulo com fallback automático de 3 camadas.

        Tier 1 → Tier 2 → Tier 3 conforme falhas ocorrem.
        Propaga exceção apenas se Tier 3 também falhar (import impossível).
        """
        # ── Tier 1: Binário Nativo (.pyd/.so) ────────────────────────────────
        # Nota: variáveis de except são deletadas no final do bloco em Python.
        # Por isso capturamos o erro em _t1 antes de sair do except.
        _t1: Optional[Exception] = None
        try:
            return super().exec_module(module)
        except Exception as _e:
            _t1 = _e
            # Remove estado parcial do módulo antes de tentar fallback
            sys.modules.pop(module.__name__, None)

        # ── Tier 2 + 3: Python (otimizado ou puro) ───────────────────────────
        if not self._py_fallback or not os.path.exists(self._py_fallback):
            # Sem fallback Python disponível → propaga o erro original
            raise ImportError(
                f"[Vulcan] Tier 1 falhou e sem fallback .py para '{module.__name__}'. "
                f"Erro original: {_t1}"
            ) from _t1

        # Tenta Tier 2 primeiro (Python otimizado), depois Tier 3 (puro)
        for _, py_path in self._iter_python_tiers():
            if not py_path or not os.path.exists(py_path):
                continue
            try:
                spec = importlib.util.spec_from_file_location(module.__name__, py_path)
                if not spec or not spec.loader:
                    continue
                py_mod = importlib.util.module_from_spec(spec)
                sys.modules[module.__name__] = py_mod
                spec.loader.exec_module(py_mod)
                # Copia atributos do módulo carregado para o módulo alvo
                module.__dict__.update(py_mod.__dict__)
                return
            except Exception:
                sys.modules.pop(module.__name__, None)
                continue

        # Todos os tiers falharam → propaga o erro original do Tier 1
        raise ImportError(
            f"[Vulcan] Todos os 3 tiers falharam para '{module.__name__}'. "
            f"Verifique o módulo ou execute 'doxoade vulcan doctor'."
        ) from _t1

    # ── Iterador de tiers Python ─────────────────────────────────────────────

    def _iter_python_tiers(self):
        """
        Gera pares (label, path) para Tier 2 e Tier 3 em ordem de prioridade.

        Tier 2 — Python otimizado (opt_cache): tenta localizar sem gerar.
        Tier 3 — Python puro original.
        """
        # Tier 2: Python otimizado
        opt = self._find_opt_py(self._py_fallback)
        yield ("tier2:opt", opt)

        # Tier 3: Python puro
        yield ("tier3:pure", self._py_fallback)

    # ── Localização do opt_py ────────────────────────────────────────────────

    @staticmethod
    def _find_opt_py(py_fallback: str) -> Optional[str]:
        """
        Localiza o Python otimizado para ``py_fallback`` no cache do projeto.

        Sobe a árvore de diretórios a partir do arquivo .py procurando
        ``.doxoade/vulcan/``. Se encontrar e o cache estiver atualizado,
        retorna o path. Caso contrário, retorna None.

        Falhas são silenciosas (retorna None) para não comprometer o fallback.
        """
        try:
            from doxoade.tools.vulcan.opt_cache import find_opt_py, find_project_root_for

            src = Path(py_fallback)
            root = find_project_root_for(src)
            if not root:
                return None

            result = find_opt_py(root, src)
            return str(result) if result else None
        except Exception:
            return None