# doxoade/tools/vulcan/compiler.py
import os, sys, subprocess, shutil
from pathlib import Path

class VulcanCompiler:
    _cached_env = None # Cache de Classe (Pitstop)

    def __init__(self, env):
        self.env = env

    def _prepare_pitstop_env(self):
        """Prepara o toolkit GCC apenas uma vez (Hefesto)."""
        if VulcanCompiler._cached_env is not None:
            return VulcanCompiler._cached_env

        # Localiza w64devkit dentro do projeto
        core_root = Path(__file__).resolve().parents[3]
        gcc_exe = core_root / "opt" / "w64devkit" / "bin" / "gcc.exe"
        
        env = os.environ.copy()
        if gcc_exe.exists():
            bin_dir = str(gcc_exe.parent)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
            env["CC"] = "gcc"
            env["CXX"] = "g++"
            env["DISTUTILS_USE_SDK"] = "1"
            env["PY_VULCAN_PITSTOP"] = "1"
            
        VulcanCompiler._cached_env = env
        return env

    def compile(self, module_name: str):
        """Compilação otimizada com flags de silício (-O3)."""
        build_env = self._prepare_pitstop_env()
        foundry_path = self.env.foundry.resolve()
        
        # Setup Dinâmico focado em performance
        setup_content = f"""
from setuptools import setup, Extension
from Cython.Build import cythonize
ext = Extension("{module_name}", ["{module_name}.pyx"], 
                extra_compile_args=['-O3', '-ffast-math', '-march=native'])
setup(ext_modules=cythonize(ext, language_level=3))
"""
        (foundry_path / "setup_tmp.py").write_text(setup_content, encoding='utf-8')

        # Comando de compilação sem carregar shell pesado
        cmd = [sys.executable, "setup_tmp.py", "build_ext", "--inplace"]
        if os.name == 'nt': cmd.append("--compiler=mingw32")

        res = subprocess.run(cmd, cwd=str(foundry_path), env=build_env, 
                             capture_output=True, text=True)
        
        if res.returncode != 0:
            return False
        return self._promote_binary(module_name)

    def _promote_binary(self, name):
        # Lógica de movimentação para .doxoade/vulcan/bin
        ext = ".pyd" if os.name == 'nt' else ".so"
        for f in self.env.foundry.glob(f"{name}*{ext}"):
            shutil.move(str(f), str(self.env.bin_dir / f"{name}{ext}"))
            return True
        return False