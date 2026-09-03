# doxoade/commands/lite_xl_systems/lite_xl_snapshots.py
"""
💀 Hades — Backup/restore de workspace, sessão e golden snapshot.
Parte do split de engine_lite_xl.py (God Class original V17.0) em módulos por responsabilidade.
"""
import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

from .lite_xl_paths import LiteXLPaths

class LiteXLSnapshots:
    """💀 Hades — Backup/restore de workspace, sessão e golden snapshot."""

    @classmethod
    def get_session_artifacts(cls) -> List[Path]:
        """Retorna todos os artefatos de sessão persistente no USERDIR."""
        user_dir = LiteXLPaths.get_user_dir()
        artifacts = []

        # 1. Diretório de workspace (splits, abas, projetos)
        ws_dir = user_dir / "workspace"
        if ws_dir.exists() and ws_dir.is_dir():
            artifacts.append(ws_dir)

        # 2. Arquivos de sessão e configurações dinâmicas
        for fname in ["session.lua", "user_settings.lua", "session.json"]:
            p = user_dir / fname
            if p.exists() and p.is_file():
                artifacts.append(p)

        return artifacts

    @classmethod
    def backup_workspace_state(cls) -> bool:
        """Cria snapshot abrangente de todos os artefatos de sessão do usuário."""
        try:
            bkp_dir = LiteXLPaths.get_workspace_backup_dir()
            bkp_dir.mkdir(parents=True, exist_ok=True)
            artifacts = cls.get_session_artifacts()

            for art in artifacts:
                dest = bkp_dir / art.name
                if art.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(art, dest, dirs_exist_ok=True)
                elif art.is_file():
                    shutil.copy2(art, dest)

            return True
        except Exception:
            return False

    @classmethod
    def restore_workspace_state(cls) -> bool:
        """Restaura o estado exato de abas, splits, session.lua e user_settings."""
        try:
            bkp_dir = LiteXLPaths.get_workspace_backup_dir()
            user_dir = LiteXLPaths.get_user_dir()
            if not bkp_dir.exists():
                return False

            for item in bkp_dir.iterdir():
                dest = user_dir / item.name
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                elif item.is_file():
                    shutil.copy2(item, dest)

            return True
        except Exception:
            return False

    @classmethod
    def promote_to_stable_snapshot(cls) -> bool:
        """Promove o init.lua atual a Golden Snapshot estável."""
        init_path = LiteXLPaths.get_init_lua_path()
        if not init_path.exists():
            return False
        try:
            stable_path = LiteXLPaths.get_stable_init_path()
            shutil.copy2(init_path, stable_path)
            return True
        except Exception:
            return False

    @classmethod
    def restore_stable_snapshot(cls) -> Tuple[bool, str]:
        """Restaura o último init.lua estável conhecido."""
        init_path = LiteXLPaths.get_init_lua_path()
        stable_path = LiteXLPaths.get_stable_init_path()

        if init_path.exists():
            try:
                broken_path = LiteXLPaths.get_broken_init_path()
                shutil.copy2(init_path, broken_path)
            except Exception:
                pass

        if stable_path.exists():
            try:
                shutil.copy2(stable_path, init_path)
                return True, "Golden Snapshot (.stable) restaurado com sucesso."
            except Exception as e:
                return False, f"Falha ao copiar snapshot estável: {e}"

        try:
            from .lite_xl_init_builder import LiteXLInitBuilder  # import tardio: quebra ciclo Snapshots<->InitBuilder
            LiteXLInitBuilder.install_sovereign_config()
            return True, "Snapshot estável inexistente. Configuração padrão instalada."
        except Exception as e:
            return False, f"Falha no fallback de emergência: {e}"
