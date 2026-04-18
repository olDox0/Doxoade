import subprocess
import os

def import_wsl_distro(distro_name, install_path, tar_gz_path):
    """Invoca o powershell.exe para importar a distro no Windows."""
    # Converte caminhos Unix (/mnt/c/...) para Windows (C:\...)
    win_install_path = subprocess.check_output(['wslpath', '-w', install_path]).decode().strip()
    win_tar_path = subprocess.check_output(['wslpath', '-w', tar_gz_path]).decode().strip()
    
    cmd = [
        'powershell.exe', '-Command',
        f'wsl --import {distro_name} "{win_install_path}" "{win_tar_path}" --version 2'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Erro no WSL Import: {result.stderr}")
    return result.stdout