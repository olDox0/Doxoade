# doxoade/tools/lua_systems/lua_config.py
# URLs oficiais e configurações
""" Configurações e URLs oficiais para runtimes Lua. """

#from pathlib import Path
from typing import Dict, List

# URLs oficiais do LuaBinaries (SourceForge)
LUA_BINARIES_BASE_URL = "https://sourceforge.net/projects/luabinaries/files"

# Versões suportadas
SUPPORTED_VERSIONS: Dict[str, Dict[str, str]] = {
    "5.4.8": {
        "win64": f"{LUA_BINARIES_BASE_URL}/5.4.8/Tools%20Executables/lua-5.4.8_Win64_bin.zip/download",
        "win32": f"{LUA_BINARIES_BASE_URL}/5.4.8/Tools%20Executables/lua-5.4.8_Win32_bin.zip/download",
        "linux": None,  # Linux geralmente tem Lua via package manager
        "macos": None,  # macOS geralmente tem Lua via Homebrew
    },
    "5.4.7": {
        "win64": f"{LUA_BINARIES_BASE_URL}/5.4.7/Tools%20Executables/lua-5.4.7_Win64_bin.zip/download",
        "win32": f"{LUA_BINARIES_BASE_URL}/5.4.7/Tools%20Executables/lua-5.4.7_Win32_bin.zip/download",
        "linux": None,
        "macos": None,
    },
    "5.3.6": {
        "win64": f"{LUA_BINARIES_BASE_URL}/5.3.6/Tools%20Executables/lua-5.3.6_Win64_bin.zip/download",
        "win32": f"{LUA_BINARIES_BASE_URL}/5.3.6/Tools%20Executables/lua-5.3.6_Win32_bin.zip/download",
        "linux": None,
        "macos": None,
    },
}

# Versão padrão (mesma do Lite XL)
DEFAULT_VERSION = "5.4.8"

# Nomes de executáveis por versão
EXECUTABLE_NAMES: Dict[str, List[str]] = {
    "5.4.8": ["lua54.exe", "lua.exe"],
    "5.4.7": ["lua54.exe", "lua.exe"],
    "5.3.6": ["lua53.exe", "lua.exe"],
}

# Diretório de instalação dentro da venv
INSTALL_DIR_NAME = "lua_runtime"
