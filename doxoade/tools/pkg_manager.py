# doxoade/tools/pkg_manager.py  (patch v2)
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

    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(packages)

    # FIX: Isola o grupo de processos no Windows.
    # Sem isso, Ctrl+C propaga SIGINT para o pip/uv filho, que imprime
    # "Comando interrompido pelo usuário. Saindo..." no terminal do Vulcan.
    extra_flags = {}
    if __import__('os').name == 'nt':
        extra_flags['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        # shell=False (Protocolo Aegis)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            **extra_flags
        )
    except subprocess.CalledProcessError as e:
        return e