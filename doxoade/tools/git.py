# doxoade/tools/git.py
import subprocess
import os
from colorama import Fore

def _run_git_command(args, capture_output=False, silent_fail=False):
    """Executa um comando git de forma segura e codificada."""
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        command = ['git'] + args
        
        result = subprocess.run(
            command, capture_output=capture_output, text=True, check=True,
            encoding='utf-8', errors='replace', env=env
        )
        return result.stdout.strip() if capture_output else True
    except (FileNotFoundError, subprocess.CalledProcessError):
        if not silent_fail:
            if not capture_output: 
                print(Fore.RED + "[ERRO GIT] O comando falhou.")
        return None

def _get_git_commit_hash(path):
    """Obtém o hash do commit atual no diretório especificado."""
    original_dir = os.getcwd()
    try:
        if os.path.exists(path):
            os.chdir(path)
        hash_output = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        return hash_output if hash_output else "N/A"
    except Exception: 
        return "N/A"
    finally: 
        os.chdir(original_dir)