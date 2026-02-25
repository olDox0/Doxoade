# -*- coding: utf-8 -*-
"""Gerador de módulo local para runtime Vulcan em projetos externos."""

from __future__ import annotations

import os
from pathlib import Path

LOCAL_VULCAN_MODULE_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Módulo local gerado pelo `doxoade vulcan module`.

Este arquivo é autocontido para funcionar em projetos que NÃO possuem
`doxoade` instalado no próprio ambiente virtual.

Uso típico no __main__.py:

    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    LOCAL_DOXOADE = ROOT / ".doxoade"
    if LOCAL_DOXOADE.exists() and str(LOCAL_DOXOADE) not in sys.path:
        sys.path.insert(0, str(LOCAL_DOXOADE))

    from vulcan.runtime import activate_vulcan
    activate_vulcan(globals(), __file__)
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _binary_ext() -> str:
    return ".pyd" if os.name == "nt" else ".so"


def install_local_vulcan_path(source_file):
    """Adiciona `<root>/.doxoade` no sys.path para permitir `from vulcan.runtime`.

    Retorna True quando o caminho foi encontrado (e inserido ou já presente).
    """
    root = find_vulcan_project_root(source_file)
    if not root:
        return False

    local_doxoade = root / ".doxoade"
    if not local_doxoade.exists():
        return False

    path_str = str(local_doxoade)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    return True


def find_vulcan_project_root(start):
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent

    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists():
            return node
    return None


def load_vulcan_binary(module_name, project_root):
    root = Path(project_root).resolve()
    bin_path = root / ".doxoade" / "vulcan" / "bin" / f"{module_name}{_binary_ext()}"
    if not bin_path.exists():
        return None

    old_path = sys.path.copy()
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

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


def activate_vulcan(globs, source_file, project_root=None, prefix="v_", optimized_suffix="_vulcan_optimized"):
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
'''


def generate_local_vulcan_module(project_root: str | os.PathLike, force: bool = False) -> tuple[bool, Path]:
    """Gera `.doxoade/vulcan/runtime.py` para consumo local do projeto alvo.

    Retorna `(created_or_updated, runtime_file_path)`.
    """
    root = Path(project_root).resolve()
    target_dir = root / ".doxoade" / "vulcan"
    runtime_file = target_dir / "runtime.py"
    init_file = target_dir / "__init__.py"

    target_dir.mkdir(parents=True, exist_ok=True)

    if runtime_file.exists() and not force:
        return False, runtime_file

    runtime_file.write_text(LOCAL_VULCAN_MODULE_TEMPLATE, encoding="utf-8")
    init_file.write_text('"""Runtime local do Vulcan para este projeto."""\n', encoding="utf-8")
    return True, runtime_file
