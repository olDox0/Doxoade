# doxoade/diagnostic/inspector.py
import sys
import os
import importlib
import platform
import shutil
from doxoade.tools.git import _run_git_command

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

    def check_git_health(self):
        """Verifica se o repositório git está saudável."""
        try:
            is_repo = _run_git_command(['rev-parse', '--is-inside-work-tree'], capture_output=True, silent_fail=True)
            if not is_repo or is_repo.strip() != 'true':
                 return {"is_git_repo": False, "status": "Not a git repository"}

            branch = _run_git_command(['branch', '--show-current'], capture_output=True, silent_fail=True)
            status = _run_git_command(['status', '--porcelain'], capture_output=True, silent_fail=True)
            last_commit = _run_git_command(['log', '-1', '--format=%h - %s'], capture_output=True, silent_fail=True)
            
            is_dirty = bool(status and status.strip())
            
            # [MELHORIA] Retorna a lista de arquivos, não só a contagem
            pending_files = []
            if status:
                for line in status.splitlines():
                    if line.strip():
                        pending_files.append(line.strip())
            
            return {
                "is_git_repo": True,
                "branch": branch.strip() if branch else "DETACHED",
                "dirty_tree": is_dirty,
                "pending_files": pending_files, # Lista real agora
                "last_commit": last_commit.strip() if last_commit else "Initial"
            }
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

    def run_full_diagnosis(self):
        return {
            "environment": self.check_environment(),
            "git": self.check_git_health(),
            "integrity": self.verify_core_modules()
        }