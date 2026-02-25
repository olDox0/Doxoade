# -*- coding: utf-8 -*-
"""Runtime bridge para consumir binários Vulcan em projetos externos.

Uso rápido no ``__main__.py`` de outro projeto::

    from doxoade.tools.vulcan.runtime import activate_vulcan

    activate_vulcan(globals(), __file__)

A função procura por ``.doxoade/vulcan/bin`` no projeto atual,
carrega ``v_<nome_do_arquivo>.pyd|.so`` e injeta funções
``*_vulcan_optimized`` sobre os nomes originais.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import MutableMapping, Optional


def _binary_ext() -> str:
    return ".pyd" if os.name == "nt" else ".so"


def find_vulcan_project_root(start: str | Path) -> Optional[Path]:
    """Localiza a raiz de projeto com ``.doxoade/vulcan/bin``."""
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent

    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists():
            return node
    return None


def load_vulcan_binary(module_name: str, project_root: str | Path) -> Optional[ModuleType]:
    """Carrega um binário Vulcan pelo nome lógico.

    ``module_name`` deve ser o nome sem extensão, por exemplo: ``v_engine``.
    """
    root = Path(project_root).resolve()
    bin_path = root / ".doxoade" / "vulcan" / "bin" / f"{module_name}{_binary_ext()}"
    if not bin_path.exists():
        return None

    old_path = sys.path.copy()
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        # Tenta também o site-packages do venv local do projeto alvo.
        venv = root / "venv"
        if venv.exists():
            if os.name == "nt":
                site_packages = venv / "Lib" / "site-packages"
            else:
                pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
                site_packages = venv / "lib" / pyver / "site-packages"
            if site_packages.exists():
                site_packages_str = str(site_packages)
                if site_packages_str not in sys.path:
                    sys.path.insert(1, site_packages_str)

        spec = importlib.util.spec_from_file_location(module_name, str(bin_path))
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None
    finally:
        sys.path = old_path


def activate_vulcan(
    globs: MutableMapping[str, object],
    source_file: str,
    *,
    project_root: str | Path | None = None,
    prefix: str = "v_",
    optimized_suffix: str = "_vulcan_optimized",
) -> bool:
    """Ativa funções otimizadas do Vulcan no escopo informado.

    Retorna ``True`` quando um binário é carregado e ao menos um símbolo é injetado.
    """
    root = Path(project_root).resolve() if project_root else find_vulcan_project_root(source_file)
    if not root:
        return False

    source_name = Path(source_file).stem
    module = load_vulcan_binary(f"{prefix}{source_name}", root)
    if not module:
        return False

    injected = 0
    for attr in dir(module):
        if not attr.endswith(optimized_suffix):
            continue
        original_name = attr[: -len(optimized_suffix)]
        globs[original_name] = getattr(module, attr)
        injected += 1

    return injected > 0
