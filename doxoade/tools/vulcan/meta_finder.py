# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/meta_finder.py (v6.1 - RAM Cached)
"""
VulcanMetaFinder - Hook Transparente de Importação.
v6.1:
- [RAM Cache] Varredura ultra-rápida em memória para evitar estrangulamento
  de I/O no disco durante a importação massiva.
- Lógica de busca por padrão para bibliotecas (lib_bin), resolvendo a
  falha de incompatibilidade de hash entre compilação e execução.
- Debug controlado por variável de ambiente (VULCAN_META_DEBUG=1).
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
    "core", "common", "base", "helpers", "config"
    # removidos: "utils", "parser", "types"  ← muito usados em click
}

def is_binary_candidate(fullname: str, pyd_path: Path) -> bool:
    basename = fullname.rsplit(".", 1)[-1]
    stem_base = pyd_path.stem.split(".")[0]

    # Para nomes genéricos, exige que o pacote pai esteja no nome do pyd
    if basename in GENERIC_NAMES:
        return stem_base.startswith(f"v_{basename}_")

    return stem_base.startswith(f"v_{basename}_") or stem_base == f"v_{basename}"

def try_load_pyd(self, fullname, py_path, bin_path):
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
        
        # Cache em RAM para anular consultas repetidas no disco rígido
        self._host_validity_cache: dict[str, bool] = {}
        self._build_ram_index()
        
        self._dlog("[VULCAN DEBUG] MetaFinder initialized with RAM Cache.")

    def _build_ram_index(self):
        """
        Lê os diretórios binários uma única vez e cria cache em RAM O(1).
        Isso elimina a necessidade de fazer glob() e exists() massivos no disco
        cada vez que o Python chama um 'import'.
        """
        self._lib_bin_files =[]
        if self.lib_bin_dir.exists():
            try:
                for f in os.scandir(self.lib_bin_dir):
                    if f.name.endswith(self._ext):
                        self._lib_bin_files.append(f.name)
            except OSError:
                pass

        self._bin_files = set()
        self._bin_stems = set()  # Para fast-fail
        if self.bin_dir.exists():
            try:
                for f in os.scandir(self.bin_dir):
                    if f.name.endswith(self._ext):
                        self._bin_files.add(f.name)
                        # Extrai o stem real (ex: v_math_a1b2c3.pyd -> math)
                        if f.name.startswith("v_") and "_" in f.name[2:]:
                            stem = f.name[2:].rsplit('_', 1)[0]
                            self._bin_stems.add(stem)
            except OSError:
                pass

    @staticmethod
    def _debug_enabled() -> bool:
        return os.environ.get("VULCAN_META_DEBUG", "").strip() == "1"

    @classmethod
    def _dlog(cls, msg: str) -> None:
        if cls._debug_enabled():
            print(msg, file=sys.stderr)

    def find_spec(self, fullname: str, path, target=None):
        try:
            if any(fullname.startswith(p) for p in self._BYPASS):
                return None

            # ── Cache unificado ─────────────────────────────────
            cached = self._spec_cache.get(fullname)
            if cached is not None:
                return cached if cached is not False else None

            module_part = fullname.split('.')[-1]

            # ── LIB_BIN: Pesquisa Rápida em RAM ────────────────────────────────
            lib_bin_enabled = os.environ.get("VULCAN_DISABLE_LIB_BIN", "0").strip() != "1"
            if lib_bin_enabled and self._lib_bin_files:
                prefix = f"v_{module_part}_"
                exact = f"v_{module_part}{self._ext}"
                
                # Onde antes havia um glob() no disco, agora lemos apenas as strings em RAM
                candidate_names =[f for f in self._lib_bin_files if f.startswith(prefix) or f == exact]

                if candidate_names:
                    candidates =[self.lib_bin_dir / f for f in candidate_names]
                    for bin_path in sorted(candidates, key=lambda p: self._get_mtime(str(p)), reverse=True):
                        if not is_binary_candidate(fullname, bin_path):
                            self._dlog(f"\033[90m[VULCAN SKIP] {bin_path.name} ≠ {fullname}\033[0m")
                            continue

                        if not self.is_binary_valid_for_host(bin_path):
                            continue

                        original_spec = self._resolve_py_path_as_spec(fullname, path)
                        self._dlog(f"[DEBUG] {fullname} → original_spec={original_spec}")
                        if not (original_spec and original_spec.loader):
                            continue

                        expected_hash = self._get_path_hash(original_spec.origin)
                        actual_hash = bin_path.stem.split(".")[0].rsplit("_", 1)[-1]
                        if actual_hash != expected_hash:
                            self._dlog(
                                f"[VULCAN SKIP] hash mismatch {fullname}: "
                                f"esperado={expected_hash}, pyd={actual_hash} ({bin_path.name})"
                            )
                            continue

                        try:
                            origin_name = Path(str(original_spec.origin)).name
                        except Exception:
                            origin_name = ""
                        if origin_name == "__init__.py":
                            self._dlog(f"[DEBUG] skip package root for {fullname}")
                            continue

                        native_name = bin_path.stem.split(".")[0]
                        from doxoade.tools.vulcan.runtime import VulcanLoader
                        new_spec = importlib.machinery.ModuleSpec(
                            fullname,
                            VulcanLoader(original_spec.loader, bin_path, native_name),
                            origin=original_spec.origin,
                        )
                        if getattr(original_spec, "submodule_search_locations", None) is not None:
                            new_spec.submodule_search_locations = original_spec.submodule_search_locations
                        new_spec.has_location = True

                        self._spec_cache[fullname] = new_spec
                        return new_spec

            # ── BIN: Arquivos de projeto compilados ────────────────────────────
            # Aborta imediatamente (Fast-Fail) se o nome do módulo não tem binário compilado.
            # Isso impede que o sistema vá procurar bibliotecas padrões do Python no disco.
            if module_part in self._bin_stems:
                py_path = self._resolve_py_path(fullname, path)
                if py_path:
                    bin_path = self._find_project_binary(py_path)
                    if bin_path and self.is_binary_valid_for_host(bin_path) and not self._is_stale(py_path, str(bin_path)):
                        self.logger.info(f"VULCAN HIT: Mapping project file '{fullname}' -> '{bin_path}'")
                        spec = self._make_spec(fullname, py_path, str(bin_path))
                        self._spec_cache[fullname] = spec
                        return spec

            # Miss - Se chegamos aqui, arquivamos o fracasso para poupar ciclos no futuro.
            if not fullname.startswith("doxoade."):
                self._spec_cache[fullname] = False
            return None

        except Exception:
            self.logger.error(f"VulcanMetaFinder.find_spec failure on '{fullname}'", exc_info=True)
            return None
            

    def _resolve_py_path_as_spec(self, fullname: str, path):
        """Retorna o spec do .py original sem acionar este finder."""
        for finder in sys.meta_path:
            if finder is self:
                continue
            if not hasattr(finder, 'find_spec'):
                continue
            try:
                spec = finder.find_spec(fullname, path, None)
                if spec and spec.origin and spec.origin not in ('built-in', 'frozen'):
                    return spec
            except Exception:
                continue
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
        if not py_path or not py_path.endswith('.py'):
            return None
        path_hash = self._get_path_hash(py_path)
        v_name = f"v_{Path(py_path).stem}_{path_hash}{self._ext}"
        
        # Fast Check em RAM no lugar do pesado .exists()
        if v_name in self._bin_files:
            return self.bin_dir / v_name
        return None

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
        bin_str = str(bin_path)
        if bin_str in self._host_validity_cache:
            return self._host_validity_cache[bin_str]

        try:
            if not bin_path.exists() or bin_path.stat().st_size < 1024: 
                self._host_validity_cache[bin_str] = False
                return False
            if os.name == 'nt':
                with bin_path.open('rb') as f:
                    if f.read(2) != b'MZ': 
                        self._host_validity_cache[bin_str] = False
                        return False
                    f.seek(0x3C)
                    pe_offset = struct.unpack('<I', f.read(4))[0]
                    f.seek(pe_offset + 4)
                    machine = struct.unpack('<H', f.read(2))[0]
                host_bits = struct.calcsize('P') * 8
                if host_bits == 64 and machine != 0x8664: 
                    self._host_validity_cache[bin_str] = False
                    return False
                if host_bits == 32 and machine != 0x014c: 
                    self._host_validity_cache[bin_str] = False
                    return False
            
            self._host_validity_cache[bin_str] = True
            return True
        except Exception:
            self._host_validity_cache[bin_str] = False
            return False

    def validate_pyd_for_export(bin_path: str, expected_init_name: str | None = None) -> bool:
        try:
            p = Path(bin_path)
            if not p.exists() or p.stat().st_size < 1024:
                return False
            lib = ctypes.CDLL(str(p))
            if expected_init_name:
                return getattr(lib, f"PyInit_{expected_init_name}", None) is not None
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
    
    uninstall()

    _ensure_vulcan_dirs(project_root)
    logfile = str(Path(project_root) / ".doxoade" / "vulcan" / "logs" / "meta_finder.log")
    logger = _setup_logger(logfile)

    _VULCAN_FINDER_INSTANCE = VulcanMetaFinder(project_root, logger)
    sys.meta_path.insert(0, _VULCAN_FINDER_INSTANCE)
    logger.info(f"VulcanMetaFinder v6.1 (RAM Cached) instalado para: {project_root}")

def uninstall():
    """Remove todas as instâncias do VulcanMetaFinder do sys.meta_path."""
    global _VULCAN_FINDER_INSTANCE
    
    original_len = len(sys.meta_path)
    sys.meta_path[:] =[f for f in sys.meta_path if not isinstance(f, VulcanMetaFinder)]
    
    if len(sys.meta_path) < original_len and _VULCAN_FINDER_INSTANCE:
        _VULCAN_FINDER_INSTANCE.logger.info("VulcanMetaFinder desinstalado.")
    
    _VULCAN_FINDER_INSTANCE = None