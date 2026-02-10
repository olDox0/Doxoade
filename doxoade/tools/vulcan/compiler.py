# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/compiler.py (v82.9 Gold)
import os
import sys
import subprocess
import shutil
from pathlib import Path
from colorama import Fore

class VulcanCompiler:
    def __init__(self, env):
        self.env = env

    def compile(self, module_name: str):
        foundry_path = self.env.foundry.resolve()
        setup_path = foundry_path / "setup_tmp.py"
        
        # 1. SETUP DE COMPILAÇÃO
        setup_content = f"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np
setup(
    ext_modules=cythonize("{module_name}.pyx", language_level=3),
    include_dirs=[np.get_include()]
)
"""
        setup_path.write_text(setup_content, encoding='utf-8')

        # 2. CONFIGURAÇÃO DE AMBIENTE (BATTERIES INCLUDED)
        core_root = Path(__file__).resolve().parents[3]
        doxo_python = core_root / "venv" / "Scripts" / "python.exe" if os.name == 'nt' else sys.executable
        opt_bin = core_root / "opt" / "w64devkit" / "bin"

        build_env = os.environ.copy()
        build_env["PYTHONPATH"] = str(core_root) + os.pathsep + build_env.get("PYTHONPATH", "")
        
        # FORÇA O GCC (MinGW) NO WINDOWS
        if os.name == 'nt' and opt_bin.exists():
            build_env["PATH"] = str(opt_bin) + os.pathsep + build_env["PATH"]
            # Variáveis que o setuptools/distutils respeitam para ignorar MSVC
            build_env["CC"] = "gcc"
            build_env["CXX"] = "g++"

        cmd = [str(doxo_python), "setup_tmp.py", "build_ext", "--inplace"]
        
        # Adiciona a flag de compilador MingW32 explicitamente no Windows
        if os.name == 'nt' and opt_bin.exists():
            cmd.append("--compiler=mingw32")

        try:
            res = subprocess.run(
                cmd, cwd=str(foundry_path), env=build_env,
                capture_output=True, text=True, encoding='utf-8', errors='replace'
            )

            if res.returncode != 0:
                print(f"{Fore.RED}   ✘ Erro de Compilação em {module_name}:")
                # Pega a essência do erro do compilador
                err = res.stderr
                if "required" in err and "Visual C++" in err:
                    print(f"{Fore.YELLOW}     [!] O Python ignorou o GCC e buscou MSVC. Tentando bypass alternativo...")
                else:
                    lines = [l for l in err.splitlines() if 'error:' in l.lower()][-3:]
                    for l in lines: print(f"     {Fore.YELLOW}{l}")
                return False

            return self._promote_binary(module_name)
        except Exception as e:
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            print(f"{Fore.RED}   ✘ Falha na Forja: {e}")
            return False

    def _promote_binary(self, module_name):
        # ... (lógica de move original preservada)
        ext = ".pyd" if os.name == 'nt' else ".so"
        for file in self.env.foundry.glob(f"{module_name}*{ext}"):
            dest = self.env.bin_dir / f"{module_name}{ext}"
            try:
                if dest.exists():
                    temp = dest.with_suffix('.old_trash')
                    if temp.exists(): temp.unlink()
                    os.rename(str(dest), str(temp))
                shutil.move(str(file), str(dest))
                return True
            except Exception as e:
                import logging as _dox_log
                import sys as exc_sys
                from traceback import print_tb as exc_trace
                _, exc_obj, exc_tb = exc_sys.exc_info()
                print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
                exc_trace(exc_tb)
                _dox_log.error(f"[INFRA] _promote_binary: {e}")
        return False