# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/meta_finder.py (v5.0 - Final Fix & Instrumented)
"""
VulcanMetaFinder - Hook Transparente de Importação.
v5.0:
- Lógica de busca por padrão para bibliotecas (lib_bin), resolvendo a
  falha de incompatibilidade de hash entre compilação e execução.
- Adicionada instrumentação com print() para depuração visível no terminal.
"""

import time
import sys
import struct
import os
import logging
import importlib.util
import importlib.abc
import hashlib
import ctypes

from pathlib import Path
from doxoade.tools.vulcan.vulcan_safe_loader import SafeExtensionLoader


GENERIC_NAMES = {
    "utils", "parser", "core", "common",
    "base", "helpers", "types", "config"
}

def is_binary_candidate(fullname: str, pyd_path: Path) -> bool:
    """
    Decide se um binário pode representar este módulo.
    Regra: o namespace COMPLETO deve estar explícito no nome do .pyd
    """
    basename = fullname.rsplit(".", 1)[-1]

    # nomes perigosos nunca entram automaticamente
    if basename in GENERIC_NAMES:
        return False

    normalized = fullname.replace(".", "_")
    return normalized in pyd_path.stem


def try_load_pyd(self, fullname, py_path, bin_path):
    try:
        bin_stem = Path(bin_path).stem

        loader = SafeExtensionLoader(
            fullname,
            bin_path,
            py_path
        )

        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=loader,
            origin=bin_path,
            is_package=False
        )

        if py_path:
            spec.submodule_search_locations = [os.path.dirname(py_path)]

        return spec

    except Exception as e:
        # 🔒 REGRA DE OURO: .pyd NUNCA QUEBRA IMPORT
        self.logger.debug(
            f"[SAFE-FALLBACK] .pyd ignorado → {fullname} ({e})"
        )
        return None  # força fallback para .py


def _ensure_vulcan_dirs(project_root: str) -> Path:
    base = Path(project_root) / ".doxoade" / "vulcan"
    logs = base / "logs"
    base.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    return base

def _setup_logger(logfile: str, level: int = logging.INFO):

    logger = logging.getLogger("vulcan.meta_finder")
    if logger.handlers: return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


class VulcanMetaFinder(importlib.abc.MetaPathFinder):
    _BYPASS = ('doxoade.tools.vulcan', 'encodings', 'codecs', '_')
    _path_hash_cache: dict[str, str] = {}
    _mtime_cache: dict[str, tuple[float, float]] = {}
    _MTIME_TTL = 2.0

    def __init__(self, project_root: str, logger=None):
        self.project_root = Path(project_root).resolve()
        self.logger = logger or logging.getLogger(__name__)
        self.lib_bin_dir = self.project_root / ".doxoade" / "vulcan" / "lib_bin"
        self.bin_dir = self.project_root / ".doxoade" / "vulcan" / "bin"
        self._spec_cache: dict[str, object] = {}
        self._ext = ".pyd" if os.name == 'nt' else ".so"
        #print(f"\033[96m[VULCAN DEBUG] MetaFinder v5.0 Initialized. Watching for imports...\033[0m", file=sys.stderr)

    def find_spec(self, fullname: str, path, target=None):
        # 🔒 REGRA DE SEGURANÇA: Vulcan só acelera o próprio domínio
        if not fullname.startswith("doxoade."):
            return None
        try:
            if any(fullname.startswith(p) for p in self._BYPASS):
                return None

            # --- ETAPA 1: BUSCA POR BIBLIOTECAS (lib_bin) ---
            # Esta é a lógica nova e corrigida
            if self.lib_bin_dir.exists():
                # Para 'click.formatting', o 'module_part' será 'formatting'
                module_part = fullname.split('.')[-1]
                pattern = f"v_{module_part}_*{self._ext}"
                
                #print(f"\033[96m[VULCAN DEBUG] Searching for library '{fullname}' with pattern '{pattern}'\033[0m", file=sys.stderr)
                
                candidates = list(self.lib_bin_dir.glob(pattern))

                for bin_path in sorted(candidates, key=os.path.getmtime, reverse=True):
                    if not is_binary_candidate(fullname, bin_path):
                        print(
                            f"\033[90m[VULCAN SKIP] {bin_path.name} ≠ {fullname}\033[0m",
                            file=sys.stderr
                        )
                        continue

                    if self.is_binary_valid_for_host(bin_path):
                        print(
                            f"\033[92m[VULCAN DEBUG] ACCEPTED binary: {bin_path.name}\033[0m",
                            file=sys.stderr
                        )
                        return self._make_spec(fullname, None, str(bin_path))

            # --- ETAPA 2: BUSCA POR ARQUIVOS DE PROJETO (bin) ---
            # (Esta lógica é para 'vulcan ignite' e permanece a mesma)
            cached = self._spec_cache.get(fullname)
            if cached is False: return None
            
            py_path = self._resolve_py_path(fullname, path)
            if not py_path:
                self._spec_cache[fullname] = False
                return None

            bin_path = self._find_project_binary(py_path)
            if bin_path and self.is_binary_valid_for_host(bin_path) and not self._is_stale(py_path, str(bin_path)):
                self.logger.info(f"VULCAN HIT: Mapping project file '{fullname}' -> '{bin_path}'")
                self._spec_cache[fullname] = (py_path, str(bin_path))
                return self._make_spec(fullname, py_path, str(bin_path))

            self._spec_cache[fullname] = False
            return None

        except Exception:
            self.logger.error(f"VulcanMetaFinder.find_spec failure on '{fullname}'", exc_info=True)
            return None

    def _resolve_py_path(self, fullname, path):
    
        for finder in sys.meta_path:
            if finder is self: continue
            if hasattr(finder, 'find_spec'):
                try:
                    spec = finder.find_spec(fullname, path, None)
                    if spec and spec.origin and spec.origin not in ('built-in', 'frozen'):
                        return spec.origin
                except Exception:
                    continue
        return None

    def _find_project_binary(self, py_path: str) -> Path | None:
        # Renomeado para clareza, esta função só lida com binários de projeto
        if not py_path or not py_path.endswith('.py'):
            return None
        path_hash = self._get_path_hash(py_path)
        v_name = f"v_{Path(py_path).stem}_{path_hash}{self._ext}"
        bin_path = self.bin_dir / v_name
        return bin_path if bin_path.exists() else None

    # (O restante das funções de utilidade como _get_path_hash, _is_stale, _make_spec, etc., permanecem as mesmas)
    # ... cole o resto do arquivo original aqui ...
    @classmethod
    def _get_path_hash(cls, path: str) -> str:
        norm_path = str(Path(path).resolve())
        if norm_path in cls._path_hash_cache:
            return cls._path_hash_cache[norm_path]
        h = hashlib.sha256(norm_path.encode('utf-8')).hexdigest()[:6]
        cls._path_hash_cache[norm_path] = h
        return h

    @classmethod
    def _get_mtime(cls, path: str) -> float:
        now = time.monotonic()
        if path in cls._mtime_cache:
            ts, mtime = cls._mtime_cache[path]
            if now - ts < cls._MTIME_TTL:
                return mtime
        try:
            mtime = Path(path).stat().st_mtime
            cls._mtime_cache[path] = (now, mtime)
            return mtime
        except OSError:
            return 0.0

    def _is_stale(self, py_path: str, bin_path: str) -> bool:
        if not py_path: return False
        py_mtime = self._get_mtime(py_path)
        bin_mtime = self._get_mtime(bin_path)
        is_stale = py_mtime > bin_mtime
        if is_stale:
            self.logger.warning(f"STALE: '{Path(bin_path).name}' is older than '{Path(py_path).name}'.")
        return is_stale

    def _make_spec(self, fullname: str, py_path, bin_path: str):
        """
        Cria o ModuleSpec para um binario Cython.

        CRITICO: ExtensionFileLoader usa 'name' para construir PyInit_<name>.
        Binarios de projeto exportam PyInit_v_pathspec_008599, NAO PyInit_pathspec.
        Passando fullname ("pathspec") causa:
            ImportError: dynamic module does not define module export function (PyInit_pathspec)

        Solucao: usar o stem real do arquivo como nome do loader.
        O ModuleSpec ainda registra fullname para que sys.modules["pathspec"] funcione.
        """
        try:
            loader = SafeExtensionLoader(
                fullname,
                bin_path,
                py_path
            )

            spec = importlib.machinery.ModuleSpec(
                name=fullname,
                loader=loader,
                origin=bin_path,
                is_package=False
            )

            if py_path:
                spec.submodule_search_locations = [os.path.dirname(py_path)]

            return spec
        except Exception:
            self.logger.error(
                f"Failed to create SAFE spec for '{fullname}' at '{bin_path}'",
                exc_info=True
            )
            return None
    def is_binary_valid_for_host(self, bin_path: Path) -> bool:
        try:
            if not bin_path.exists() or bin_path.stat().st_size < 1024: return False
            if os.name == 'nt':
                with bin_path.open('rb') as f:
                    if f.read(2) != b'MZ': return False
                    f.seek(0x3C)
                    pe_offset = struct.unpack('<I', f.read(4))[0]
                    f.seek(pe_offset + 4)
                    machine = struct.unpack('<H', f.read(2))[0]
                host_bits = struct.calcsize('P') * 8
                if host_bits == 64 and machine != 0x8664: return False
                if host_bits == 32 and machine != 0x014c: return False
            return True
        except Exception:
            return False

    def validate_pyd_for_export(bin_path: str, expected_init_name: str | None = None) -> bool:
        """
        Verifica se o .pyd exporta PyInit_<expected> ou qualquer PyInit_.* 
        Retorna True se parece válido para este host.
        """
        try:
            p = Path(bin_path)
            if not p.exists() or p.stat().st_size < 1024:
                return False
            # tenta abrir sem executar init (só para ver símbolos)
            lib = ctypes.CDLL(str(p))
            # se tiver expected_init_name, checa explicitamente
            if expected_init_name:
                return getattr(lib, f"PyInit_{expected_init_name}", None) is not None
            # fallback: tenta localizar qualquer PyInit_ prefixado
            # (note: ctypes não lista símbolos; este é heurístico e pode falhar)
            # se a carga foi bem-sucedida, assume válido
            return True
        except (OSError, Exception):
            return False

_VULCAN_FINDER_INSTANCE = None

def install(project_root: str):
    """
    Instala o VulcanMetaFinder para a raiz de projeto especificada.
    Força a remoção de qualquer finder anterior para garantir o contexto correto.
    """
    global _VULCAN_FINDER_INSTANCE
    
    # PASSO CRUCIAL: Remove qualquer finder antigo para evitar conflito de contexto.
    uninstall()

    _ensure_vulcan_dirs(project_root)
    logfile = str(Path(project_root) / ".doxoade" / "vulcan" / "logs" / "meta_finder.log")
    logger = _setup_logger(logfile)

    _VULCAN_FINDER_INSTANCE = VulcanMetaFinder(project_root, logger)
    sys.meta_path.insert(0, _VULCAN_FINDER_INSTANCE)
    logger.info(f"VulcanMetaFinder v6.0 (Context-Forced) instalado para: {project_root}")

def uninstall():
    """Remove todas as instâncias do VulcanMetaFinder do sys.meta_path."""
    global _VULCAN_FINDER_INSTANCE
    
    original_len = len(sys.meta_path)
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, VulcanMetaFinder)]
    
    if len(sys.meta_path) < original_len and _VULCAN_FINDER_INSTANCE:
        _VULCAN_FINDER_INSTANCE.logger.info("VulcanMetaFinder desinstalado.")
    
    _VULCAN_FINDER_INSTANCE = None