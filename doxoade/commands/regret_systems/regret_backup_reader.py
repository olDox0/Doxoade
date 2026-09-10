# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_backup_reader.py
"""
📦 Leitor Blindado de Snapshots do Doxoade Backup para Análise de Regressão.
Implementa cache em memória por sessão, thread-safety com Mutex Lock e
descompressão atômica para prevenir Access Violation (NT 0xC0000005) no Windows.
"""
from __future__ import annotations
import gc
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Dict

try:
    from doxoade.commands.backup_systems.backup_cmd import (
        _load_backup_text_chain,
        _latest_backup_id,
        _resolve_backup_id,
        _normalize_rel_path,
    )
    from doxoade.commands.backup_systems.backup_engine import BackupEngineStrap
    BACKUP_ENGINE_AVAILABLE = True
except ImportError:
    BACKUP_ENGINE_AVAILABLE = False


class RegretBackupReader:
    """Extrai arquivos de backups do Doxoade com blindagem de concorrência e cache."""

    _LOCK = threading.Lock()
    _TEXT_CACHE: Dict[Tuple[str, str], Optional[str]] = {}  # (backup_id, rel_path) -> text

    @classmethod
    def get_backup_dir(cls, project_root: Optional[Path] = None) -> Path:
        root = project_root or Path.cwd()
        return root / ".doxoade" / "backups"

    @classmethod
    def get_latest_backup_id(cls, project_root: Optional[Path] = None) -> Optional[str]:
        if not BACKUP_ENGINE_AVAILABLE:
            return None
        root = project_root or Path.cwd()
        backup_dir = cls.get_backup_dir(root)
        try:
            engine = BackupEngineStrap(root, backup_dir)
            return _latest_backup_id(engine)
        except Exception:
            return None

    @classmethod
    def get_file_content_from_backup(
        cls,
        file_path: Path,
        backup_id: Optional[str] = None,
        project_root: Optional[Path] = None
    ) -> Tuple[Optional[str], str]:
        """
        Extrai o texto descomprimido de um arquivo do backup de forma atômica e cacheada.
        Retorna (conteudo_texto, backup_id_utilizado).
        """
        if not BACKUP_ENGINE_AVAILABLE:
            return None, "BACKUP_ENGINE_UNAVAILABLE"

        root = project_root or Path.cwd()
        backup_dir = cls.get_backup_dir(root)

        if not backup_id:
            backup_id = cls.get_latest_backup_id(root)
            if not backup_id:
                return None, "NO_BACKUP_FOUND"

        try:
            rel = _normalize_rel_path(root, str(file_path))
        except Exception as e:
            return None, str(e)

        cache_key = (backup_id, rel)
        with cls._LOCK:
            if cache_key in cls._TEXT_CACHE:
                cached_val = cls._TEXT_CACHE[cache_key]
                return cached_val, backup_id

            try:
                # Expulsa ponteiros C zumbis antes de abrir o stream
                gc.collect()
                status, text = _load_backup_text_chain(backup_dir, backup_id, rel)
                if status == "ok" and text is not None:
                    cls._TEXT_CACHE[cache_key] = text
                    return text, backup_id

                cls._TEXT_CACHE[cache_key] = None
                return None, f"STATUS_{status.upper()}"
            except (PermissionError, OSError, Exception) as e:
                cls._TEXT_CACHE[cache_key] = None
                return None, str(e)
            finally:
                # Limpeza defensiva pós-descompressão
                gc.collect()

    @classmethod
    def clear_cache(cls) -> None:
        """Limpa o cache de textos extraídos da sessão."""
        with cls._LOCK:
            cls._TEXT_CACHE.clear()
            gc.collect()
