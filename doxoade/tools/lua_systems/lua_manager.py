# doxoade/tools/lua_systems/lua_manager.py
# Gerenciador de runtimes instalados
""" Gerenciador de runtimes Lua instalados. """

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
from .lua_config import DEFAULT_VERSION, EXECUTABLE_NAMES # INSTALL_DIR_NAME
from .lua_installer import LuaInstaller


class LuaRuntimeManager:
    """Gerencia múltiplas versões de Lua e fornece interface unificada."""

    @staticmethod
    def find_lua_runtime(preferred_version: str = DEFAULT_VERSION) -> Optional[Tuple[Path, str]]:
        """
        Encontra um runtime Lua disponível.
        
        Busca na ordem:
        1. Instalação gerenciada pelo doxoade
        2. PATH do sistema
        3. Locais comuns (Program Files, etc)
        
        Returns:
            Tupla (path_para_executavel, versao) ou None se não encontrar.
        """
        # 1. Instalação gerenciada
        install_dir = LuaInstaller.get_install_dir()
        if install_dir.exists():
            possible_names = EXECUTABLE_NAMES.get(preferred_version, ["lua.exe", "lua54.exe"])
            for exe_name in possible_names:
                exe_path = install_dir / exe_name
                if exe_path.exists():
                    version = LuaRuntimeManager._detect_version(exe_path)
                    return exe_path, version
        
        # 2. PATH do sistema
        for name in ["lua", "lua54", "lua53", "lua52", "luajit"]:
            p = shutil.which(name)
            if p:
                exe_path = Path(p)
                version = LuaRuntimeManager._detect_version(exe_path)
                return exe_path, version
        
        # 3. Locais comuns (Windows)
        if sys.platform == "win32":
            common_paths = [
                Path("C:/Program Files/Lua/5.4/lua54.exe"),
                Path("C:/Program Files (x86)/Lua/5.4/lua54.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Lua\lua54.exe")),
            ]
            for path in common_paths:
                if path.exists():
                    version = LuaRuntimeManager._detect_version(path)
                    return path, version
        
        return None

    @staticmethod
    def _detect_version(exe_path: Path) -> str:
        """Detecta a versão do Lua executando 'lua -v'."""
        try:
            result = subprocess.run(
                [str(exe_path), "-v"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (result.stdout + result.stderr).strip()
            # Extrai versão do formato "Lua 5.4.8  Copyright..."
            for line in output.splitlines():
                if "Lua" in line and any(c.isdigit() for c in line):
                    parts = line.split()
                    for part in parts:
                        if part[0].isdigit() and "." in part:
                            return part
            return "versão desconhecida"
        except Exception:
            return "versão desconhecida"

    @classmethod
    def ensure_lua_runtime(cls, version: str = DEFAULT_VERSION, auto_install: bool = True) -> Optional[Tuple[Path, str]]:
        """
        Garante que um runtime Lua esteja disponível.
        
        Se não encontrar e auto_install=True, instala automaticamente.
        
        Returns:
            Tupla (path, versao) ou None se não conseguir garantir.
        """
        # Tentar encontrar
        runtime = cls.find_lua_runtime(version)
        if runtime:
            return runtime
        
        # Auto-instalar se permitido
        if auto_install and sys.platform == "win32":
            print("⚠ Runtime Lua não encontrado. Instalando automaticamente...")
            exe_path = LuaInstaller.install_lua(version)
            if exe_path:
                detected_version = cls._detect_version(exe_path)
                return exe_path, detected_version
        
        return None

    @classmethod
    def list_installed_versions(cls) -> List[Tuple[Path, str]]:
        """Lista todas as versões do Lua instaladas."""
        versions = []
        
        # Instalação gerenciada
        install_dir = LuaInstaller.get_install_dir()
        if install_dir.exists():
            for exe in install_dir.glob("*.exe"):
                if "lua" in exe.name.lower():
                    version = cls._detect_version(exe)
                    versions.append((exe, version))
        
        return versions

    @classmethod
    def compile_check(cls, lua_file: Path, preferred_version: str = DEFAULT_VERSION) -> Optional[str]:
        """
        Verifica compilação de um arquivo Lua usando o runtime.
        
        Returns:
            Mensagem de erro ou None se OK.
        """
        runtime = cls.find_lua_runtime(preferred_version)
        if not runtime:
            return "NO_RUNTIME"
        
        exe_path, version = runtime
        
        probe = (
            "local f,err=loadfile(arg[1]) "
            "if not f then io.write(err) os.exit(1) end"
        )
        
        try:
            result = subprocess.run(
                [str(exe_path), probe, str(lua_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return result.stdout.strip() or result.stderr.strip() or "compile error"
            
            return None
            
        except Exception as e:
            return f"runtime probe failed: {e}"
