# doxoade/commands/lite_xl_systems/lite_xl_paths.py
"""
🗺️ Zeus — Resolução de caminhos, estrutura de diretórios e runtime Lua do Lite XL.
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

try:
    from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager
except ImportError:
    try:
        from doxoade.tools.lua_systems import LuaRuntimeManager
    except ImportError:
        LuaRuntimeManager = None

class LiteXLPaths:
    """🗺️ Zeus — Resolução de caminhos, estrutura de diretórios e runtime Lua do Lite XL."""

    @staticmethod
    def get_user_dir() -> Path:
        home = Path.home()
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        if xdg_config and (Path(xdg_config) / "lite-xl").exists():
            return Path(xdg_config) / "lite-xl"

        dot_config = home / ".config" / "lite-xl"
        if dot_config.exists():
            return dot_config

        if sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata and (Path(appdata) / "lite-xl").exists():
                return Path(appdata) / "lite-xl"

        return dot_config

    @classmethod
    def get_template_dir(cls) -> Path:
        return Path(__file__).parent / "template"

    @classmethod
    def get_init_lua_path(cls) -> Path:
        return cls.get_user_dir() / "init.lua"

    @classmethod
    def get_session_log_path(cls) -> Path:
        return cls.get_user_dir() / "session_log.txt"

    @classmethod
    def get_error_txt_path(cls) -> Path:
        return cls.get_user_dir() / "error.txt"

    @classmethod
    def get_ipc_queue_path(cls) -> Path:
        return cls.get_user_dir() / ".ipc_queue"

    @classmethod
    def get_probe_dir(cls) -> Path:
        """Diretório de probes do API Guard."""
        return cls.get_template_dir() / "lite_xl_probes"

    @classmethod
    def get_probe_files(cls) -> List[Path]:
        """Retorna todos os probes Lua de forma ordenada."""
        p_dir = cls.get_probe_dir()
        if not p_dir.exists():
            return []
        return sorted([f for f in p_dir.glob("*.lua") if f.is_file()])

    @classmethod
    def get_sandbox_dir(cls) -> Path:
        """Diretório de configuração isolado exclusivo para testes."""
        sandbox_dir = cls.get_user_dir() / ".doxoade" / "sandbox"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        return sandbox_dir

    @classmethod
    def get_workspace_dir(cls) -> Path:
        """Diretório de sessões e abas do Lite XL."""
        return cls.get_user_dir() / "workspace"

    @classmethod
    def get_workspace_backup_dir(cls) -> Path:
        """Diretório de segurança para snapshots de sessão do Doxoade."""
        return cls.get_user_dir() / ".doxoade" / "workspace_backup"

    @classmethod
    def get_stable_init_path(cls) -> Path:
        """Retorna o caminho do snapshot estável (Golden State)."""
        return cls.get_init_lua_path().with_suffix(".lua.stable")

    @classmethod
    def get_broken_init_path(cls) -> Path:
        """Retorna o caminho de quarentena do init que falhou."""
        return cls.get_init_lua_path().with_suffix(".lua.broken")

    @classmethod
    def bootstrap_templates_if_missing(cls):
        """Garante que a pasta de templates modular exista no sistema."""
        t_dir = cls.get_template_dir()
        t_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_lua_manager(cls):
        """Obtém a classe LuaRuntimeManager com fallback seguro de importação."""
        global LuaRuntimeManager
        if LuaRuntimeManager is not None:
            return LuaRuntimeManager
        try:
            from doxoade.tools.lua_systems.lua_manager import LuaRuntimeManager as LRM
            LuaRuntimeManager = LRM
            return LuaRuntimeManager
        except Exception:
            return None

    @classmethod
    def _find_lua_runtime(cls) -> Optional[str]:
        """Encontra runtime Lua usando o sistema de gestão."""
        manager = cls._get_lua_manager()
        if not manager:
            return None
        runtime = manager.find_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def ensure_lua_runtime(cls) -> Optional[str]:
        """Garante que um runtime Lua esteja disponível, instalando se necessário."""
        manager = cls._get_lua_manager()
        if not manager:
            return None
        runtime = manager.ensure_lua_runtime()
        return str(runtime[0]) if runtime else None

    @classmethod
    def lua_runtime_info(cls) -> Optional[Tuple[str, str]]:
        """Retorna (caminho_do_lua, banner_de_versao) ou None se ausente."""
        lua = cls._find_lua_runtime()
        if not lua:
            return None
        try:
            res = subprocess.run([lua, "-v"], capture_output=True, text=True, timeout=5)
            banner = (res.stdout + res.stderr).strip()
            version = banner.splitlines()[0] if banner else "versão desconhecida"
            return lua, version
        except Exception:
            return lua, "versão desconhecida"
