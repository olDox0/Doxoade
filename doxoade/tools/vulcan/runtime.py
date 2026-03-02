# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/runtime.py
"""Runtime bridge para consumir binários Vulcan em projetos externos.

Uso recomendado no ``__main__.py`` de outro projeto:

    from doxoade.tools.vulcan.runtime import activate_vulcan
    activate_vulcan(globals(), __file__)

Este módulo foi escrito para ser defensivo: não falha na importação
mesmo se o pacote doxoade não estiver instalado no ambiente alvo.
"""

from __future__ import annotations

import sys
import struct
import os
import importlib
import importlib.util
import importlib.abc

from typing import MutableMapping, Optional
from types import ModuleType
from pathlib import Path

try:
    from doxoade.tools.vulcan.import_translate import ImportTranslator
except Exception:
    ImportTranslator = None

def _is_binary_candidate(fullname: str, bin_path: Path) -> bool:
    normalized = fullname.replace(".", "_")
    return normalized in bin_path.stem

def inject_namespace(alias: str, real: str):
    """
    Registra alias em sys.modules apontando para módulo real.
    Se o módulo real não existir, apenas retorna sem erro.
    """
    if alias in sys.modules:
        return
    try:
        mod = importlib.import_module(real)
    except Exception:
        return
    sys.modules[alias] = mod

# Só tenta ajustar namespaces se estivermos *dentro* do doxoade (import possível)
try:
    # evita falha quando runtime é usado em projeto externo sem doxoade instalado
    inject_namespace("doxoade.commands.tools", "doxoade.tools")
    inject_namespace("doxoade.commands.shared_tools", "doxoade.shared_tools")
except Exception:
    # silencioso
    pass

# Instala ImportTranslator apenas se disponível e seguro
try:
    if ImportTranslator is not None and not any(isinstance(x, ImportTranslator) for x in sys.meta_path):
        translator = ImportTranslator(base_dir=Path(__file__).parent, mapping={
            "doxoade.commands.tools": "doxoade.commands.shared_tools",
            "doxoade.commands.shared_tools": "doxoade.commands.shared_tools",
        })
        sys.meta_path.insert(0, translator)
except Exception:
    # não queremos falhar aqui
    translator = None  # type: ignore

class VulcanBinaryFinder(importlib.abc.MetaPathFinder):
    """Finder que prioriza binários Vulcan durante imports Python."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.bin_dir = self.project_root / ".doxoade" / "vulcan" / "bin"

    def _candidates(self, fullname: str) -> list[str]:
        parts = fullname.split(".")
        candidates: list[str] = []

        # 1) Nome completo (mais restritivo)
        candidates.append("v_" + "_".join(parts))

        # 2) Remoção progressiva de prefixos (ex: package_sub_module -> sub_module)
        for i in range(1, len(parts)):
            candidates.append("v_" + "_".join(parts[i:]))

        # 3) Último nome apenas (fallback)
        if parts:
            candidates.append("v_" + parts[-1])

        # preserva ordem e remove duplicados
        return list(dict.fromkeys(candidates))

    def _resolve_source_for_fullname(self, fullname: str) -> Path | None:
        rel = Path(*fullname.split('.'))
        py_file = self.project_root / f"{rel}.py"
        if py_file.exists():
            return py_file
        init_file = self.project_root / rel / "__init__.py"
        if init_file.exists():
            return init_file
        return None

    def find_spec(self, fullname: str, path=None, target=None):
        # não interferir em imports do próprio doxoade (internos)
        if fullname.startswith("doxoade."):
            return None
        if not self.bin_dir.exists():
            return None

        candidates = self._candidates(fullname)
        if os.environ.get("VULCAN_DEBUG"):
            print(f"[VULCAN DEBUG] finder: fullname={fullname} candidates={candidates}")

        ext = _binary_ext()
        for base_name in candidates:
            candidate = self.bin_dir / f"{base_name}{ext}"
            if not candidate.exists():
                continue

            source_path = self._resolve_source_for_fullname(fullname)
            if not _is_binary_valid_for_host(candidate) or not _is_binary_fresh(candidate, source_path):
                continue

            spec = importlib.util.spec_from_file_location(fullname, str(candidate))
            if spec and spec.loader:
                return spec

        return None

def _binary_ext() -> str:
    return ".pyd" if os.name == "nt" else ".so"

def _is_binary_valid_for_host(bin_path: Path) -> bool:
    try:
        if not bin_path.exists() or bin_path.stat().st_size < 4096:
            return False
        with bin_path.open('rb') as f:
            head = f.read(64)
        if os.name == 'nt':
            if not head.startswith(b'MZ'):
                return False
            with bin_path.open('rb') as f:
                f.seek(0x3C)
                e_lfanew = struct.unpack('<I', f.read(4))[0]
                f.seek(e_lfanew + 4)
                machine = struct.unpack('<H', f.read(2))[0]
            host_bits = struct.calcsize('P') * 8
            if host_bits == 64 and machine != 0x8664:
                return False
            if host_bits == 32 and machine != 0x014c:
                return False
        else:
            if not head.startswith(b'\x7fELF'):
                return False
        return True
    except Exception:
        return False

def _is_binary_fresh(bin_path: Path, source_path: Path | None) -> bool:
    if not source_path or not source_path.exists():
        return True
    try:
        return bin_path.stat().st_mtime >= source_path.stat().st_mtime
    except OSError:
        return False

def find_vulcan_project_root(start: str | Path) -> Optional[Path]:
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists():
            return node
    return None

def load_vulcan_binary(module_name: str, project_root: str | Path) -> Optional[ModuleType]:
    root = Path(project_root).resolve()
    bin_path = root / ".doxoade" / "vulcan" / "bin" / f"{module_name}{_binary_ext()}"
    if not bin_path.exists() or not _is_binary_valid_for_host(bin_path):
        return None

    old_path = sys.path.copy()
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        # tenta site-packages do venv local (se presente)
        venv = root / "venv"
        if venv.exists():
            if os.name == "nt":
                site_packages = venv / "Lib" / "site-packages"
            else:
                pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
                site_packages = venv / "lib" / pyver / "site-packages"
            if site_packages.exists():
                sp = str(site_packages)
                if sp not in sys.path:
                    sys.path.insert(1, sp)

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

    Protegido: não lança exceções para o processo do projeto alvo.
    """
    try:
        root = Path(project_root).resolve() if project_root else find_vulcan_project_root(source_file)
        if not root:
            return False

        source_path = Path(source_file)
        source_name = source_path.stem
        if source_name == "__main__":
            source_name = source_path.parent.name

        finder = VulcanBinaryFinder(root)
        if not any(isinstance(existing, VulcanBinaryFinder) and existing.project_root == finder.project_root
                   for existing in sys.meta_path):
            sys.meta_path.insert(0, finder)

        # determina nome lógico do binário baseado no módulo corrente
        module_name = globs.get("__name__", source_name)
        module_name = module_name.replace(".", "_")

        # primeira tentativa: v_<module_name>
        module = load_vulcan_binary(f"{prefix}{module_name}", root)
        if not module:
            # fallback: v_<source_name> (menos restrito)
            module = load_vulcan_binary(f"{prefix}{source_name}", root)
        if not module:
            return False

        injected = 0
        for attr in dir(module):
            if not attr.endswith(optimized_suffix):
                continue
            original_name = attr[:-len(optimized_suffix)]
            globs[original_name] = getattr(module, attr)
            injected += 1

        # opcional: marca de sucesso (apenas quando debug ativo)
        if injected and os.environ.get("VULCAN_DEBUG"):
            print(f"[VULCAN DEBUG] injected {injected} symbol(s) from {module.__name__}")

        return injected > 0
    except Exception:
        # NÃO propagar erro ao processo alvo
        if os.environ.get("VULCAN_DEBUG"):
            import traceback as _tb
            _tb.print_exc()
        return False
