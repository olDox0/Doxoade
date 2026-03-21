# -*- coding: utf-8 -*-
# doxoade/commands/vulcan/site-packages.py
"""Helpers para resolução de site-packages no contexto Vulcan."""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path


# ── Nomes de diretório de venv convencionais a procurar ──────────────────────
_VENV_NAMES = ("venv", "Venv", ".venv", "env", "Env")


def _find_active_venv_site_packages() -> list[str]:
    """
    Resolve o(s) diretório(s) site-packages do venv realmente ativo.

    Estratégia (em ordem de prioridade):
      1. $VIRTUAL_ENV — mas somente se o caminho existir no disco.
         VIRTUAL_ENV pode apontar para um venv obsoleto/diferente quando o
         usuário muda de projeto sem abrir um novo terminal.
      2. Busca pelo venv relativo ao projeto atual (cwd → acima):
         Procura por <raiz>/<nome_venv>/Lib/site-packages onde <nome_venv>
         é um dos nomes convencionais (venv, Venv, .venv, env, Env).
         Isso resolve o caso onde VIRTUAL_ENV aponta para o caminho errado
         mas o venv correto está na mesma árvore do projeto.
    """
    from pathlib import Path as _P

    def _sp_from_venv_root(venv_root: _P) -> list[str]:
        """Retorna site-packages válidos dentro de um root de venv."""
        result: list[str] = []
        # Windows
        win_sp = venv_root / "Lib" / "site-packages"
        if win_sp.is_dir():
            result.append(str(win_sp))
        # Linux/macOS
        lib = venv_root / "lib"
        if lib.is_dir():
            for p in sorted(lib.glob("python*/site-packages")):
                if p.is_dir():
                    result.append(str(p))
        return result

    # ── 1. $VIRTUAL_ENV (somente se existir) ──────────────────────────────────
    venv_env = os.environ.get("VIRTUAL_ENV")
    if venv_env:
        venv_path = _P(venv_env)
        if venv_path.is_dir():
            dirs = _sp_from_venv_root(venv_path)
            if dirs:
                return dirs
        # VIRTUAL_ENV definido mas inválido — continua para fallback

    # ── 2. Busca relativa ao projeto (cwd → raiz) ─────────────────────────────
    search_start = _P(os.getcwd())
    # Sobe até 6 níveis procurando um diretório de venv convencional
    current = search_start
    for _ in range(6):
        for venv_name in _VENV_NAMES:
            candidate = current / venv_name
            if candidate.is_dir():
                dirs = _sp_from_venv_root(candidate)
                if dirs:
                    return dirs
        parent = current.parent
        if parent == current:
            break
        current = parent

    return []
    """Retorna os diretórios site-packages do venv dado."""
    dirs: list[str] = []
    venv_path = Path(venv)

    # Windows: Lib/site-packages
    win_site = venv_path / "Lib" / "site-packages"
    if win_site.is_dir():
        dirs.append(str(win_site))

    # Linux/macOS: lib/pythonX.Y/site-packages
    lib_path = venv_path / "lib"
    if lib_path.is_dir():
        for p in sorted(lib_path.glob("python*/site-packages")):
            if p.is_dir():
                dirs.append(str(p))

    return dirs


def ensure_venv_in_syspath() -> list[str]:
    """
    Garante que o site-packages do venv realmente ativo está em sys.path.

    Usa _find_active_venv_site_packages() que valida o path antes de usar
    (evita o caso onde VIRTUAL_ENV aponta para um venv obsoleto/inexistente).
    """
    injected: list[str] = []
    for d in _find_active_venv_site_packages():
        if d not in sys.path:
            sys.path.insert(0, d)
            injected.append(d)
    return injected


# ── Injeta automaticamente ao importar este módulo ────────────────────────────
# Necessário porque doxoade pode ser o executável global e o pacote-alvo
# (ex: llama_cpp) só existe no venv.  A injeção precoce garante que qualquer
# chamada subsequente a importlib.util.find_spec() ou importlib.metadata já
# enxerga o site-packages correto.
_INJECTED_AT_IMPORT = ensure_venv_in_syspath()


def site_packages_dirs_for_listing() -> list[str]:
    """Resolve diretórios de libs priorizando o venv realmente ativo.

    Usa _find_active_venv_site_packages() que valida o VIRTUAL_ENV antes de
    usá-lo e faz fallback para busca relativa ao projeto quando necessário.
    """
    dirs = _find_active_venv_site_packages()
    if dirs:
        return dirs

    # Último recurso: site do Python atual
    try:
        dirs.extend(site.getsitepackages())
    except AttributeError:
        pass

    try:
        user_sp = site.getusersitepackages()
        if user_sp:
            dirs.append(user_sp)
    except AttributeError:
        pass

    for p in sys.path:
        if "site-packages" in p or "dist-packages" in p:
            dirs.append(p)

    seen: set[str] = set()
    return [d for d in dirs if d and not (d in seen or seen.add(d))]