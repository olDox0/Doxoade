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
        """Busca exaustiva pelo melhor compilador disponível."""
        # 1. Tenta GCC (Padrão Doxoade via w64devkit)
        gcc = shutil.which("gcc")
        if gcc:
            self.compiler_path = gcc
            self.type = "gcc"
            return True
            
        # 2. Busca interna no Doxoade (w64devkit embarcado)
        # Sobe ate a raiz do doxoade para procurar em thirdparty
        core_root = Path(__file__).resolve().parents[3]
        internal_gcc = core_root / "thirdparty" / "w64devkit" / "bin" / "gcc.exe"
        if internal_gcc.exists():
            self.compiler_path = str(internal_gcc)
            self.type = "gcc"
            # Injeta no PATH para os subprocessos
            os.environ["PATH"] = str(internal_gcc.parent) + os.pathsep + os.environ.get("PATH", "")
            return True
            
        return False

    def get_version(self):
        import subprocess
        if not self.compiler_path: return "N/A"
        res = subprocess.run([self.compiler_path, "--version"], capture_output=True, text=True)
        return res.stdout.splitlines()[0]