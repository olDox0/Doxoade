# doxoade/doxoade/diagnostic/inspector.py
import sys
import os
import importlib
import platform
import shutil
from doxoade.tools.git import _run_git_command, _get_detailed_diff_stats, _get_last_commit_info

class SystemInspector:

    @staticmethod
    def _resolve_git_cwd(target_path: str=None):
        """Resolve diretório-base para comandos git em diagnose por caminho."""
        if not target_path:
            return None
        p = os.path.abspath(target_path)
        if os.path.isdir(p):
            return p
        if os.path.isfile(p):
            return os.path.dirname(p)
        return None

    def check_environment(self):
        """Coleta dados vitais do ambiente de execução."""
        env_venv = os.environ.get('VIRTUAL_ENV')
        sys_venv = sys.prefix != sys.base_prefix
        is_venv = bool(env_venv or sys_venv)
        venv_path = env_venv if env_venv else sys.prefix if sys_venv else sys.executable
        if not is_venv:
            exe_lower = sys.executable.lower()
            cwd_lower = os.getcwd().lower()
            if cwd_lower in exe_lower and ('venv' in exe_lower or 'scripts' in exe_lower):
                is_venv = True
                venv_path = sys.prefix
        pkg_manager = 'pip'
        if shutil.which('poetry'):
            pkg_manager = 'poetry'
        elif shutil.which('uv'):
            pkg_manager = 'uv'
        return {'python_version': sys.version.split()[0], 'os': platform.system(), 'release': platform.release(), 'arch': platform.machine(), 'venv_active': is_venv, 'venv_path': venv_path, 'cwd': os.getcwd(), 'package_manager': pkg_manager}

    def check_git_health(self, detailed: bool=False, show_code: bool=False, target_path: str=None):
        """Verifica o repositório com suporte a foco em path específico."""
        try:
            git_cwd = self._resolve_git_cwd(target_path)
            is_repo = _run_git_command(['rev-parse', '--is-inside-work-tree'], capture_output=True, silent_fail=True, cwd=git_cwd)
            if not is_repo or is_repo.strip() != 'true':
                return {'is_git_repo': False}
            branch = _run_git_command(['branch', '--show-current'], capture_output=True, silent_fail=True, cwd=git_cwd)
            status_cmd = ['status', '--porcelain']
            if target_path:
                status_cmd.extend(['--', target_path])
            status = _run_git_command(status_cmd, capture_output=True, silent_fail=True, cwd=git_cwd)
            git_data = {'is_git_repo': True, 'branch': branch.strip() if branch else 'HEAD', 'dirty_tree': bool(status and status.strip()), 'pending_count': len(status.splitlines()) if status else 0, 'last_commit_info': _get_last_commit_info(cwd=git_cwd)}
            if detailed and git_data['dirty_tree']:
                git_data['changes'] = _get_detailed_diff_stats(show_code=show_code, target_path=target_path, cwd=git_cwd)
            else:
                git_data['pending_files'] = [l.strip() for l in status.splitlines()] if status else []
            if not target_path:
                git_data['origin_main_delta'] = self._get_origin_main_delta(git_data['branch'])
            return git_data
        except Exception as e:
            return {'is_git_repo': False, 'error': str(e)}

    def _get_origin_main_delta(self, branch_name: str):
        """Coleta diferença entre origin/main e branch atual."""
        _run_git_command(['fetch', 'origin', 'main'], capture_output=True, silent_fail=True)
        base_ref = 'origin/main'
        ahead = _run_git_command(['rev-list', '--count', f'{base_ref}..HEAD'], capture_output=True, silent_fail=True) or '0'
        behind = _run_git_command(['rev-list', '--count', f'HEAD..{base_ref}'], capture_output=True, silent_fail=True) or '0'
        updates_raw = _run_git_command(['log', '--oneline', f'{base_ref}..HEAD'], capture_output=True, silent_fail=True) or ''
        updates = [line.strip() for line in updates_raw.splitlines() if line.strip()]
        changed_raw = _run_git_command(['diff', '--name-status', f'{base_ref}..HEAD'], capture_output=True, silent_fail=True) or ''
        changed = [line.strip() for line in changed_raw.splitlines() if line.strip()]
        return {'base_ref': base_ref, 'branch': branch_name or 'HEAD', 'ahead': int(ahead) if str(ahead).isdigit() else 0, 'behind': int(behind) if str(behind).isdigit() else 0, 'updates': updates[:20], 'changed_files': changed[:30]}

    def verify_core_modules(self):
        """Verifica a integridade dos módulos principais."""
        modules = ['doxoade.cli', 'doxoade.database', 'doxoade.chronos', 'doxoade.tools.git', 'doxoade.tools.logger', 'doxoade.tools.filesystem', 'doxoade.tools.analysis']
        results = {}
        for mod in modules:
            try:
                importlib.import_module(mod)
                results[mod] = 'OK'
            except ImportError as e:
                results[mod] = f'MISSING ({e})'
            except Exception as e:
                results[mod] = f'CRASH ({e})'
        return results

    def run_full_diagnosis(self, detailed: bool=False, show_code: bool=False, target_path: str=None):
        return {'environment': self.check_environment(), 'git': self.check_git_health(detailed=detailed, show_code=show_code, target_path=target_path), 'integrity': self.verify_core_modules()}