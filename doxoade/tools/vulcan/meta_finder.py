# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/meta_finder.py (perf patch v2)
"""
VulcanMetaFinder - Hook Transparente de Importação.

Otimizações v2:
 - Cache duplo: fullname -> resultado (evita _resolve_py_path para misses conhecidos)
 - Hash sha256 cacheado em nível de classe (path nunca muda durante a sessão)
 - mtime cacheado por par (py, bin) com TTL de 2s (evita stat() em loop de import)
 - _resolve_py_path agora usa iteração lazy com break imediato
"""
import sys
import os
import hashlib
import importlib.util
import importlib.abc
import importlib.machinery
import logging
# [DOX-UNUSED] import json
import struct
import time
from pathlib import Path
# [DOX-UNUSED] from copy import deepcopy

# ------------------------------------------------------------------
# Helpers de arquivos / paths
# ------------------------------------------------------------------
def _ensure_vulcan_dirs(project_root: str) -> Path:
    base = Path(project_root) / ".doxoade" / "vulcan"
    logs = base / "logs"
    base.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    return base

def _setup_logger(logfile: str, level: int = logging.INFO):
    logger = logging.getLogger("vulcan.meta_finder")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger

# ------------------------------------------------------------------
# VulcanMetaFinder
# ------------------------------------------------------------------
class VulcanMetaFinder(importlib.abc.MetaPathFinder):
    _BYPASS = ('doxoade.tools.vulcan', 'encodings', 'codecs', '_')

    # Cache de classe: hash sha256 por path absoluto (imutável durante a sessão)
    _path_hash_cache: dict[str, str] = {}
    # Cache de classe: mtime por path com timestamp de leitura (TTL 2s)
    _mtime_cache: dict[str, tuple[float, float]] = {}
    _MTIME_TTL = 2.0  # segundos

    def __init__(self, project_root: str, logger=None):
        self.project_root = Path(project_root)
        self.bin_dir = self.project_root / ".doxoade" / "vulcan" / "bin"
        self._ext = ".pyd" if os.name == 'nt' else ".so"
        self.logger = logger or logging.getLogger(__name__)

        # Cache de instância: fullname -> (py_path, bin_path) | False
        # Keyed por fullname (string) para evitar _resolve_py_path em misses
        self._spec_cache: dict[str, object] = {}

    def find_spec(self, fullname: str, path, target=None):
        try:
            # Bypass rápido para módulos do sistema
            if any(fullname.startswith(p) for p in self._BYPASS):
                return None

            # OTIMIZAÇÃO 1: cache por fullname — evita _resolve_py_path em misses conhecidos.
            # Antes: mesmo módulo sem .pyd executava _resolve_py_path + sha256 a cada import.
            cached = self._spec_cache.get(fullname)
            if cached is False:
                return None  # Miss conhecido — retorna imediatamente
            if cached is not None:
                py_path, bin_path = cached
                if Path(bin_path).exists() and not self._is_stale(py_path, bin_path):
                    return self._make_spec(fullname, py_path, bin_path)
                # Stale — invalida e re-resolve abaixo
                del self._spec_cache[fullname]

            # Resolve o .py original (custo alto — só chegamos aqui na primeira vez)
            py_path = self._resolve_py_path(fullname, path)
            if not py_path:
                self._spec_cache[fullname] = False
                return None

            bin_path = self._find_binary(py_path)
            if bin_path and not self._is_stale(py_path, str(bin_path)):
                self._spec_cache[fullname] = (py_path, str(bin_path))
                return self._make_spec(fullname, py_path, str(bin_path))

            # Sem binário disponível — cacheia o miss para não tentar de novo
            self._spec_cache[fullname] = False
            return None

        except Exception:
            self.logger.error("VulcanMetaFinder.find_spec failure", exc_info=True)
            return None

    def _resolve_py_path(self, fullname, path):
        """
        Encontra o .py original consultando os outros finders do meta_path.
        OTIMIZAÇÃO: break imediato ao primeiro resultado válido (era loop completo antes).
        """
        for finder in sys.meta_path:
            if finder is self:
                continue
            if not hasattr(finder, 'find_spec'):
                continue
            try:
                spec = finder.find_spec(fullname, path, None)
                if spec and spec.origin and spec.origin != 'built-in':
                    return spec.origin
            except Exception:
                continue
        return None

    def _find_binary(self, py_path_str: str) -> Path | None:
        """Procura o binário usando hash cacheado (OTIMIZAÇÃO 2: sha256 não é recalculado)."""
        py_path = Path(py_path_str)
        path_hash = self._get_path_hash(py_path)
        pattern   = f"v_{py_path.stem}_{path_hash}{self._ext}"
        bin_path  = self.bin_dir / pattern
        return bin_path if bin_path.exists() else None

    @classmethod
    def _get_path_hash(cls, py_path: Path) -> str:
        """
        OTIMIZAÇÃO 2: sha256 cacheado em nível de classe.
        O hash de um path nunca muda durante a sessão — recalcular a cada
        import era o segundo maior gargalo identificado na telemetria.
        """
        key = str(py_path.resolve())
        if key not in cls._path_hash_cache:
            cls._path_hash_cache[key] = hashlib.sha256(key.encode()).hexdigest()[:6]
        return cls._path_hash_cache[key]

    @classmethod
    def _get_mtime(cls, path_str: str) -> float:
        """
        OTIMIZAÇÃO 3: mtime cacheado com TTL de 2s.
        _is_stale era chamado com dois stat() a cada hit de cache válido.
        Durante uma sequência rápida de imports do mesmo módulo, o arquivo
        não muda — o TTL evita syscalls redundantes.
        """
        now = time.monotonic()
        entry = cls._mtime_cache.get(path_str)
        if entry and (now - entry[1]) < cls._MTIME_TTL:
            return entry[0]
        try:
            mtime = Path(path_str).stat().st_mtime
        except OSError:
            mtime = 0.0
        cls._mtime_cache[path_str] = (mtime, now)
        return mtime

    def _is_stale(self, py_path: str, bin_path: str) -> bool:
        return self._get_mtime(py_path) > self._get_mtime(bin_path)

    def _make_spec(self, fullname, py_path, bin_path):
        return importlib.util.spec_from_file_location(
            fullname,
            bin_path,
            submodule_search_locations=None
        )

    # ------------------------------------------------------------------
    # Validação de binário (mantida intacta)
    # ------------------------------------------------------------------
    def is_binary_valid_for_host(self, bin_path: str) -> bool:
        try:
            p = Path(bin_path)
            if not p.exists():
                return False
            if p.stat().st_size < 16 * 1024:
                return False
            if os.name == 'nt':
                with p.open('rb') as f:
                    if f.read(2) != b'MZ':
                        return False
                    f.seek(0x3C)
                    e_lfanew_bytes = f.read(4)
                    if len(e_lfanew_bytes) < 4:
                        return False
                    e_lfanew = struct.unpack("<I", e_lfanew_bytes)[0]
                    f.seek(e_lfanew + 4)
                    machine_bytes = f.read(2)
                    if len(machine_bytes) < 2:
                        return False
                    machine   = struct.unpack("<H", machine_bytes)[0]
                    host_bits = struct.calcsize("P") * 8
                    if host_bits == 64 and machine != 0x8664:
                        return False
                    if host_bits == 32 and machine != 0x014c:
                        return False
            else:
                with p.open('rb') as f:
                    if f.read(4) != b'\x7fELF':
                        return False
            return True
        except Exception:
            if self.logger:
                self.logger.exception("Binary validation failed: %s", bin_path)
            return False

    def get_metrics(self):
        return {
            "spec_cache_size":      len(self._spec_cache),
            "spec_cache_hits":      sum(1 for v in self._spec_cache.values() if v is not False),
            "spec_cache_misses":    sum(1 for v in self._spec_cache.values() if v is False),
            "path_hash_cache_size": len(self._path_hash_cache),
            "mtime_cache_size":     len(self._mtime_cache),
        }

    def flush_metrics(self):
        pass  # métricas estão em memória, nada a persistir


# ------------------------------------------------------------------
# Lifecycle functions
# ------------------------------------------------------------------
_installed_finder = None

def install(project_root):
    global _installed_finder
    if _installed_finder:
        return

    base_dir = _ensure_vulcan_dirs(project_root)
    log_file = base_dir / "logs" / "meta_finder.log"
    logger   = _setup_logger(str(log_file))

    finder = VulcanMetaFinder(project_root, logger=logger)
    sys.meta_path.insert(0, finder)
    _installed_finder = finder

def uninstall():
    global _installed_finder
    if _installed_finder and _installed_finder in sys.meta_path:
        sys.meta_path.remove(_installed_finder)
        _installed_finder = None