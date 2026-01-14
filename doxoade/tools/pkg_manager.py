# doxoade/tools/pkg_manager.py
import subprocess
import shutil

def get_best_installer():
    """Detecta se o 'uv' está disponível, caso contrário retorna 'pip'."""
    return "uv" if shutil.which("uv") else "pip"

def run_install(packages: list, venv_python: str = None, upgrade: bool = False):
    """Executa a instalação usando o melhor motor disponível."""
    installer = get_best_installer()
    cmd = []

    if installer == "uv":
        cmd = ["uv", "pip", "install"]
        if venv_python:
            cmd.extend(["--python", venv_python])
    else:
        import sys
        py_exe = venv_python or sys.executable
        cmd = [py_exe, "-m", "pip", "install"]

    if upgrade: cmd.append("--upgrade")
    cmd.extend(packages)
    
    try:
        # shell=False (Protocolo Aegis)
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        return e