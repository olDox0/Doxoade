# doxoade/tools/lua_systems/lua_installer.py
# Download e instalação de binários Lua
""" Instalador de runtimes Lua com download automático. """

#import os
import sys
import shutil
import zipfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple
from .lua_config import SUPPORTED_VERSIONS, DEFAULT_VERSION, EXECUTABLE_NAMES, INSTALL_DIR_NAME


class LuaInstaller:
    """Instala runtimes Lua a partir de binários oficiais."""

    @staticmethod
    def get_install_dir() -> Path:
        """Retorna o diretório de instalação dentro da venv."""
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        return scripts_dir / INSTALL_DIR_NAME

    @staticmethod
    def get_platform_key() -> str:
        """Retorna a chave de plataforma (win64, win32, linux, macos)."""
        if sys.platform == "win32":
            import struct
            return "win64" if struct.calcsize("P") * 8 == 64 else "win32"
        elif sys.platform == "linux":
            return "linux"
        elif sys.platform == "darwin":
            return "macos"
        return "unknown"

    @classmethod
    def download_lua(cls, version: str = DEFAULT_VERSION) -> Optional[Path]:
        """
        Baixa o binário Lua da fonte oficial.
        
        Returns:
            Path para o arquivo ZIP baixado, ou None se falhar.
        """
        platform = cls.get_platform_key()
        url = SUPPORTED_VERSIONS.get(version, {}).get(platform)
        
        if not url:
            print(f"⚠ Nenhuma URL disponível para Lua {version} em {platform}")
            return None
        
        print(f"⬇ Baixando Lua {version} ({platform})...")
        print(f"  URL: {url}")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = Path(tmp.name)
                
                # Download com progresso
                urllib.request.urlretrieve(url, tmp_path)
                
                print(f"✔ Download concluído: {tmp_path}")
                return tmp_path
                
        except Exception as e:
            print(f"✖ Erro no download: {e}")
            return None

    @classmethod
    def install_from_zip(cls, zip_path: Path, version: str = DEFAULT_VERSION) -> Optional[Path]:
        """
        Extrai e instala o binário Lua a partir de um ZIP.
        
        Returns:
            Path para o executável instalado, ou None se falhar.
        """
        install_dir = cls.get_install_dir()
        install_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📦 Extraindo para: {install_dir}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(install_dir)
            
            # Encontrar o executável
            possible_names = EXECUTABLE_NAMES.get(version, ["lua.exe", "lua54.exe"])
            
            for exe_name in possible_names:
                exe_path = install_dir / exe_name
                if exe_path.exists():
                    print(f"✔ Lua instalado: {exe_path}")
                    return exe_path
            
            # Buscar recursivamente
            for exe_name in possible_names:
                for found in install_dir.rglob(exe_name):
                    print(f"✔ Lua encontrado: {found}")
                    return found
            
            print(f"✖ Executável não encontrado em {install_dir}")
            return None
            
        except Exception as e:
            print(f"✖ Erro na extração: {e}")
            return None

    @classmethod
    def install_lua(cls, version: str = DEFAULT_VERSION, force: bool = False) -> Optional[Path]:
        """
        Instala o Lua completo (download + extração).
        
        Args:
            version: Versão do Lua a instalar
            force: Forçar reinstalação mesmo se já existir
        
        Returns:
            Path para o executável instalado, ou None se falhar.
        """
        install_dir = cls.get_install_dir()
        possible_names = EXECUTABLE_NAMES.get(version, ["lua.exe", "lua54.exe"])
        
        # Verificar se já existe
        if not force:
            for exe_name in possible_names:
                exe_path = install_dir / exe_name
                if exe_path.exists():
                    print(f"✔ Lua {version} já instalado: {exe_path}")
                    return exe_path
        
        # Download
        zip_path = cls.download_lua(version)
        if not zip_path:
            return None
        
        try:
            # Instalação
            exe_path = cls.install_from_zip(zip_path, version)
            return exe_path
            
        finally:
            # Limpar temporário
            try:
                zip_path.unlink()
            except Exception:
                pass

    @classmethod
    def uninstall_lua(cls) -> bool:
        """Remove a instalação do Lua."""
        install_dir = cls.get_install_dir()
        
        if install_dir.exists():
            try:
                shutil.rmtree(install_dir)
                print(f"✔ Lua desinstalado: {install_dir}")
                return True
            except Exception as e:
                print(f"✖ Erro na desinstalação: {e}")
                return False
        
        print("ℹ Nenhuma instalação encontrada")
        return True
