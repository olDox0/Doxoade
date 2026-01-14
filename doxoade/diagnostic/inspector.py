# doxoade/diagnostic/inspector.py
import sys
import os
import importlib
import platform
import shutil
from ..tools.git import (
    _run_git_command,
    _get_detailed_diff_stats,
    _get_last_commit_info
)
#from doxoade.tools.git import (

class SystemInspector:
    
    def check_environment(self):
        """Coleta dados vitais do ambiente de execução."""
        # 1. Detecção por Variável de Ambiente (Definida pelo script 'activate')
        # É a prova mais forte de que o usuário "ativou" o venv no terminal.
        env_venv = os.environ.get("VIRTUAL_ENV")
        
        # 2. Detecção Interna do Python (Prefixos)
        sys_venv = sys.prefix != sys.base_prefix
        
        is_venv = bool(env_venv or sys_venv)
        
        # Determina o caminho do Venv para exibição
        venv_path = env_venv if env_venv else (sys.prefix if sys_venv else sys.executable)

        # 3. Fallback: Se não detectou, mas o executável está dentro de uma pasta 'venv' local
        if not is_venv:
            # Normaliza caminhos para evitar problemas de case no Windows
            exe_lower = sys.executable.lower()
            cwd_lower = os.getcwd().lower()
            # Se o caminho do python contém o diretório atual E 'venv' ou 'scripts'
            if cwd_lower in exe_lower and ("venv" in exe_lower or "scripts" in exe_lower):
                is_venv = True
                venv_path = sys.prefix

        # Detecta gerenciador de pacotes
        pkg_manager = "pip"
        if shutil.which("poetry"): pkg_manager = "poetry"
        elif shutil.which("uv"): pkg_manager = "uv"
        
        return {
            "python_version": sys.version.split()[0],
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "venv_active": is_venv,
            "venv_path": venv_path,
            "cwd": os.getcwd(),
            "package_manager": pkg_manager
        }

    def check_git_health(self, detailed: bool = False, show_code: bool = False, target_path: str = None):
        """Verifica o repositório com suporte a foco em path específico."""
        try:
            # Verifica se é repo
            is_repo = _run_git_command(['rev-parse', '--is-inside-work-tree'], capture_output=True, silent_fail=True)
            if not is_repo or is_repo.strip() != 'true': return {"is_git_repo": False}

            branch = _run_git_command(['branch', '--show-current'], capture_output=True, silent_fail=True)
            
            # Status filtrado por path se fornecido
            status_cmd = ['status', '--porcelain']
            if target_path: status_cmd.extend(['--', target_path])
            status = _run_git_command(status_cmd, capture_output=True, silent_fail=True)
            
            git_data = {
                "is_git_repo": True,
                "branch": branch.strip() if branch else "HEAD",
                "dirty_tree": bool(status and status.strip()),
                "pending_count": len(status.splitlines()) if status else 0,
                "last_commit_info": _get_last_commit_info()
            }

            if detailed and git_data['dirty_tree']:
                git_data['changes'] = _get_detailed_diff_stats(show_code=show_code, target_path=target_path)
            else:
                git_data['pending_files'] = [l.strip() for l in status.splitlines()] if status else []

            return git_data
        except Exception as e:
            return {"is_git_repo": False, "error": str(e)}

    def verify_core_modules(self):
        """Verifica a integridade dos módulos principais."""
        modules = [
            'doxoade.cli',
            'doxoade.database',
            'doxoade.chronos',
            'doxoade.tools.git',
            'doxoade.tools.logger',
            'doxoade.tools.filesystem',
            'doxoade.tools.analysis'
        ]
        results = {}
        for mod in modules:
            try:
                importlib.import_module(mod)
                results[mod] = "OK"
            except ImportError as e:
                results[mod] = f"MISSING ({e})"
            except Exception as e:
                results[mod] = f"CRASH ({e})"
        return results

    def run_full_diagnosis(self, detailed: bool = False, show_code: bool = False, target_path: str = None):
        return {
            "environment": self.check_environment(),
            "git": self.check_git_health(detailed=detailed, show_code=show_code, target_path=target_path),
            "integrity": self.verify_core_modules()
        }