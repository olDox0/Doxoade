# doxoade/commands/git_systems/git_engine.py
"""
Git Engine - O Motor de Sincronização e Restauração Soberana (Osíris / Ares).
Responsável por: Matriz de Colisão, Subscrição Segura (--subscribe), Pull Seletivo e Reset Hard.
Compliance: ProDeNov, PASC-8.4, OSL-4.
"""
import os
import subprocess
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command


class GitEngine:
    """Motor de operações resilientes do Git."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or os.getcwd()).resolve()

    def get_current_branch(self) -> str:
        branch = _run_git_command(['branch', '--show-current'], capture_output=True, cwd=str(self.root))
        if branch and branch.strip():
            return branch.strip()
        head = _run_git_command(['rev-parse', '--short', 'HEAD'], capture_output=True, cwd=str(self.root))
        return (head or 'HEAD').strip()

    def get_remote_tracking(self, branch: str) -> Optional[str]:
        tracking = _run_git_command(
            ['rev-parse', '--abbrev-ref', f'{branch}@{{u}}'],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        )
        return tracking.strip() if (tracking and tracking.strip()) else None

    def is_dirty(self) -> bool:
        status = _run_git_command(['status', '--porcelain'], capture_output=True, cwd=str(self.root))
        return bool(status and status.strip())

    def fetch_remote(self, remote: str = 'origin', branch: Optional[str] = None) -> Tuple[bool, str]:
        cmd = ['fetch', remote]
        if branch:
            cmd.append(branch)
        try:
            out = _run_git_command(cmd, capture_output=True, cwd=str(self.root))
            return True, (out or "Fetch concluído com sucesso.")
        except Exception as e:
            return False, f"Falha no git fetch: {e}"

    def detect_collisions(self, remote: str = 'origin', branch: Optional[str] = None) -> Dict[str, Any]:
        """Gera a Matriz de Colisão comparando working tree local com o remote."""
        current_branch = branch or self.get_current_branch()
        remote_ref = f"{remote}/{current_branch}"

        # 1. Arquivos locais com modificação não commitada
        status_raw = _run_git_command(['status', '--porcelain'], capture_output=True, cwd=str(self.root)) or ''
        local_dirty: Dict[str, str] = {}
        for line in status_raw.splitlines():
            if line.strip():
                code = line[:2].strip()
                path = line[3:].strip().strip('"').replace('\\', '/')
                local_dirty[path] = code

        # 2. Arquivos alterados no remote
        diff_raw = _run_git_command(
            ['diff', '--name-status', f'HEAD..{remote_ref}'],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        ) or ''
        remote_changes: Dict[str, str] = {}
        for line in diff_raw.splitlines():
            if line.strip():
                parts = line.split('\t')
                code = parts[0][0]
                path = parts[1].strip().strip('"').replace('\\', '/')
                remote_changes[path] = code

        # 3. Classificação
        collisions = []
        for f, loc_code in local_dirty.items():
            if f in remote_changes:
                collisions.append({
                    'file': f,
                    'local_status': loc_code,
                    'remote_status': remote_changes[f]
                })

        safe_remote = [
            {'file': f, 'remote_status': code}
            for f, code in remote_changes.items()
            if f not in local_dirty
        ]

        local_only = [
            {'file': f, 'local_status': code}
            for f, code in local_dirty.items()
            if f not in remote_changes
        ]

        return {
            'remote_ref': remote_ref,
            'branch': current_branch,
            'collisions': collisions,
            'safe_remote': safe_remote,
            'local_only': local_only,
            'total_collisions': len(collisions),
            'total_safe_remote': len(safe_remote),
            'total_local_only': len(local_only)
        }

    def subscribe_safe_remote(
        self,
        remote: str = 'origin',
        branch: Optional[str] = None,
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """
        Subscreve/sobrescreve todas as atualizações seguras do servidor no disco,
        preservando 100% das modificações locais em outros arquivos.
        """
        matrix = self.detect_collisions(remote=remote, branch=branch)
        remote_ref = matrix['remote_ref']
        safe_items = matrix['safe_remote']

        report = {
            'remote_ref': remote_ref,
            'total_to_update': len(safe_items),
            'safe_items': safe_items,
            'preserved_items': matrix['local_only'],
            'collisions_prevented': matrix['collisions'],
            'updated_files': [],
            'failed_files': [],
            'apply': apply_changes
        }

        if not apply_changes or not safe_items:
            return report

        # Extrai os arquivos do remote em lotes de 20 para evitar estouro de comando
        batch_size = 20
        to_checkout = [item['file'] for item in safe_items if item['remote_status'] != 'D']
        to_delete = [item['file'] for item in safe_items if item['remote_status'] == 'D']

        for i in range(0, len(to_checkout), batch_size):
            batch = to_checkout[i:i + batch_size]
            cmd = ['checkout', remote_ref, '--'] + batch
            ok = _run_git_command(cmd, capture_output=True, cwd=str(self.root))
            if ok:
                report['updated_files'].extend(batch)
            else:
                report['failed_files'].extend(batch)

        for del_file in to_delete:
            del_path = self.root / del_file
            if del_path.exists():
                try:
                    os.remove(del_path)
                    report['updated_files'].append(del_file + " (Removido)")
                except Exception:
                    report['failed_files'].append(del_file)

        return report

    def get_file_diff(self, file_path: str, remote: str = 'origin', branch: Optional[str] = None) -> str:
        """Obtém o diff entre a versão local atual e a versão do servidor."""
        current_branch = branch or self.get_current_branch()
        remote_ref = f"{remote}/{current_branch}"
        norm_path = file_path.replace('\\', '/')

        diff_out = _run_git_command(
            ['diff', f'{remote_ref}', '--', norm_path],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        )
        return diff_out or "(Nenhuma diferença encontrada ou arquivo novo)"

    def pull_selective_files(
        self,
        files: List[str],
        remote: str = 'origin',
        branch: Optional[str] = None,
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """Puxa apenas arquivos específicos do remote."""
        current_branch = branch or self.get_current_branch()
        remote_ref = f"{remote}/{current_branch}"

        report = {
            'target_files': files,
            'remote_ref': remote_ref,
            'apply': apply_changes,
            'success_files': [],
            'failed_files': []
        }

        if not apply_changes:
            return report

        for f in files:
            norm_path = f.replace('\\', '/')
            ok = _run_git_command(['checkout', remote_ref, '--', norm_path], capture_output=True, cwd=str(self.root))
            if ok:
                report['success_files'].append(norm_path)
            else:
                report['failed_files'].append(norm_path)

        return report

    def force_pull_reset(
        self,
        branch: Optional[str] = None,
        remote: str = 'origin',
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """Executa o Reset Hard Global."""
        current_branch = branch or self.get_current_branch()
        remote_ref = f"{remote}/{current_branch}"

        fetch_ok, fetch_msg = self.fetch_remote(remote=remote, branch=current_branch)
        if not fetch_ok:
            return {'success': False, 'mode': 'APPLY' if apply_changes else 'DRY-RUN', 'error': fetch_msg}

        tracking = self.get_remote_tracking(current_branch)
        matrix = self.detect_collisions(remote=remote, branch=current_branch)

        report = {
            'branch': current_branch,
            'remote': remote,
            'remote_ref': remote_ref,
            'tracking_configured': bool(tracking),
            'matrix': matrix,
            'is_dirty': self.is_dirty(),
            'mode': 'APPLY' if apply_changes else 'DRY-RUN',
            'plan_executed': None,
            'success': True,
            'actions_taken': []
        }

        if not apply_changes:
            return report

        try:
            if not tracking:
                _run_git_command(['branch', f'--set-upstream-to={remote_ref}', current_branch], capture_output=True, cwd=str(self.root))
                report['actions_taken'].append(f"Upstream vinculado: {remote_ref}")

            _run_git_command(['reset', '--hard', remote_ref], capture_output=True, cwd=str(self.root))
            report['actions_taken'].append(f"Reset Hard aplicado para {remote_ref}")
            report['plan_executed'] = "PLANO A (Standard Upstream + Hard Reset)"
            return report
        except Exception as err_plan_a:
            try:
                _run_git_command(['checkout', '-B', current_branch, remote_ref], capture_output=True, cwd=str(self.root))
                report['actions_taken'].append(f"[FALLBACK] Checkout forçado sobre {remote_ref}")
                report['plan_executed'] = f"PLANO B (Fallback: {err_plan_a})"
                return report
            except Exception as err_plan_b:
                report['success'] = False
                report['error'] = f"Falha no Plano A ({err_plan_a}) e Plano B ({err_plan_b})"
                return report
