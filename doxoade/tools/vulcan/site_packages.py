# -*- coding: utf-8 -*-
"""Helpers para resolução de site-packages no contexto Vulcan."""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path


def site_packages_dirs_for_listing() -> list[str]:
    """Resolve diretórios de libs priorizando o venv ativo no terminal.

    Se `VIRTUAL_ENV` estiver definido e os diretórios de site-packages do venv
    existirem, retorna apenas esses diretórios para evitar contaminação por
    ambientes globais/host em modo embedded.
    """
    dirs: list[str] = []

    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        venv_path = Path(venv)
        win_site = venv_path / "Lib" / "site-packages"
        if win_site.is_dir():
            dirs.append(str(win_site))

        lib_path = venv_path / "lib"
        if lib_path.is_dir():
            for p in sorted(lib_path.glob("python*/site-packages")):
                if p.is_dir():
                    dirs.append(str(p))

    if dirs:
        return dirs

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

    seen = set()
    return [d for d in dirs if d and not (d in seen or seen.add(d))]
