# doxoade/tools/metalcraft/metal_toolchain.py
import shutil
import os
from pathlib import Path

class NexusToolchain:
    """Especialista em detecção de compiladores e SDKs."""
    
    def __init__(self):
        self.compiler_path = None
        self.type = None # gcc | clang | msvc

    def detect(self):
        # 1. Tenta o GCC global
        gcc = shutil.which("gcc")
        if gcc:
            self.compiler_path = gcc
            return True
            
        # 2. Busca na estrutura industrial do Doxoade
        core_root = Path(__file__).resolve().parents[3]
        # O provisionador coloca o bin logo abaixo da pasta w64devkit
        internal_gcc = core_root / "thirdparty" / "w64devkit" / "bin" / "gcc.exe"
        
        if internal_gcc.exists():
            self.compiler_path = str(internal_gcc)
            # Injeta o bin no PATH para que o GCC ache o 'as' (assembler) e o 'ld' (linker)
            os.environ["PATH"] = str(internal_gcc.parent) + os.pathsep + os.environ.get("PATH", "")
            return True
        return False

    def get_version(self):
        import subprocess
        if not self.compiler_path: return "N/A"
        res = subprocess.run([self.compiler_path, "--version"], capture_output=True, text=True)
        return res.stdout.splitlines()[0]