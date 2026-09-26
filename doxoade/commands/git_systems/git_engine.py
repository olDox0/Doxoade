# -*- coding: utf-8 -*-
# doxoade/commands/git_systems/git_engine.py
"""
Git Engine - O Motor de Sincronização e Restauração Soberana (Osíris / Ares) v3.0.
Responsável por: Identificação de Estação, Auto-Snapshot Preventivo, Auto-Cura de MERGE_HEAD,
Matriz de Colisão, Subscrição Segura (--subscribe) e Smart Pull Reconciliado.
Compliance: ProDeNov, PASC-8.4, OSL-4.
"""
from __future__ import annotations

import os
import sys
import time
import shutil
import platform
import subprocess
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command


class GitEngine:
    """Motor de operações resilientes do Git com inteligência multi-máquina."""

    def __init__(self, root: Optional[str | Path] = None):
        self.root = Path(root or os.getcwd()).resolve()
        self.recovery_dir = self.root / ".doxoade" / "git_recovery"

    @staticmethod
    def get_station_name() -> str:
        """Identifica a máquina atual de forma sanitizada (ex: 'bluebaby', 'pc-a')."""
        name = platform.node().lower().replace(" ", "_").strip()
        return name if name else "station"

    def create_safety_snapshot(self, reason: str = "pre_sync") -> Optional[Path]:
        """
        🛡️ SOTÉRIA / HADES: Grava backup físico dos arquivos modificados/untracked
        antes de qualquer operação arriscada do Git.
        """
        try:
            status_raw = _run_git_command(['status', '--porcelain'], capture_output=True, cwd=str(self.root))
            if not status_raw or not status_raw.strip():
                return None  # Diretório limpo, sem risco de perda

            self.recovery_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            station = self.get_station_name()
            snapshot_dir = self.recovery_dir / f"snapshot_{station}_{timestamp}_{reason}"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            files_saved = 0
            for line in status_raw.splitlines():
                if len(line) > 3:
                    rel_path = line[3:].strip().strip('"').replace("\\", "/")
                    if " -> " in rel_path:
                        rel_path = rel_path.split(" -> ")[1]

                    src_file = self.root / rel_path
                    if src_file.exists() and src_file.is_file():
                        dest_file = snapshot_dir / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(src_file), str(dest_file))
                        files_saved += 1

            # Auto-prune: mantém no máximo os 8 últimos snapshots
            snapshots = sorted(self.recovery_dir.glob("snapshot_*"), key=lambda p: p.stat().st_mtime)
            if len(snapshots) > 8:
                for old in snapshots[:-8]:
                    shutil.rmtree(str(old), ignore_errors=True)

            return snapshot_dir if files_saved > 0 else None
        except Exception:
            return None

    def heal_stuck_merge(self) -> bool:
        """
        🩺 Auto-Cura: Detecta e resolve MERGE_HEAD órfão que bloqueia o git pull.
        Retorna True se havia um merge travado e ele foi sanado.
        """
        merge_head = self.root / ".git" / "MERGE_HEAD"
        if not merge_head.exists():
            return False

        # Cria snapshot de segurança antes de limpar
        self.create_safety_snapshot(reason="auto_heal_merge")
        
        # Tenta abortar formalmente pelo Git
        ok = _run_git_command(['merge', '--abort'], capture_output=True, silent_fail=True, cwd=str(self.root))
        if not ok or merge_head.exists():
            # Força remoção cirúrgica do lock órfão se o git recusou
            try:
                merge_head.unlink(missing_ok=True)
                merge_msg = self.root / ".git" / "MERGE_MSG"
                merge_msg.unlink(missing_ok=True)
                merge_mode = self.root / ".git" / "MERGE_MODE"
                merge_mode.unlink(missing_ok=True)
            except Exception:
                pass

        return True

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
        status_raw = _run_git_command(['status', '--porcelain'], capture_output=True, cwd=str(self.root)) or ''
        local_dirty: Dict[str, str] = {}
        for line in status_raw.splitlines():
            if line.strip():
                code = line[:2].strip()
                path = line[3:].strip().strip('"').replace('\\', '/')
                local_dirty[path] = code

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

    def smart_pull_sync(self, remote: str = 'origin', branch: Optional[str] = None, apply_changes: bool = False) -> Dict[str, Any]:
        """
        ⚡ SMART PULL SOBERANO (Multi-Station Resilient):
        1. Auto-cura de MERGE_HEAD.
        2. Snapshot de segurança dos arquivos locais.
        3. Se houver rascunhos locais sem colisão direta, faz auto-stash.
        4. Puxa atualizações do servidor.
        5. Restaura rascunhos locais por cima sem perder nada.
        """
        current_branch = branch or self.get_current_branch()
        healed_merge = self.heal_stuck_merge()
        self.fetch_remote(remote=remote, branch=current_branch)

        matrix = self.detect_collisions(remote=remote, branch=current_branch)
        has_collisions = matrix['total_collisions'] > 0
        is_locally_dirty = self.is_dirty()

        report = {
            'station': self.get_station_name(),
            'branch': current_branch,
            'remote': remote,
            'healed_merge': healed_merge,
            'matrix': matrix,
            'has_collisions': has_collisions,
            'is_dirty': is_locally_dirty,
            'snapshot': None,
            'success': False,
            'mode': 'APPLY' if apply_changes else 'DRY-RUN',
            'action_summary': ''
        }

        if not apply_changes:
            return report

        # Grava snapshot de resgate antes de tocar no código
        snapshot_dir = self.create_safety_snapshot(reason="smart_pull")
        report['snapshot'] = str(snapshot_dir) if snapshot_dir else None

        # Se houver colisão de conteúdo no mesmo arquivo, não quebra: avisa para abrir o merge
        if has_collisions:
            report['success'] = False
            report['action_summary'] = f"Colisão detectada em {matrix['total_collisions']} arquivo(s). Use 'doxoade merge' para resolver."
            return report

        # Fluxo limpo com auto-stash
        stashed = False
        if is_locally_dirty:
            stash_msg = f"doxoade_autostash_{self.get_station_name()}_{int(time.time())}"
            out = _run_git_command(['stash', 'push', '-u', '-m', stash_msg], capture_output=True, cwd=str(self.root))
            stashed = "Saved working directory" in str(out)

        pull_res = _run_git_command(['pull', '--rebase', remote, current_branch], capture_output=True, silent_fail=True, cwd=str(self.root))
        
        # Se rebase falhar (históricos muito divergentes), tenta merge padrão
        if not pull_res:
            _run_git_command(['rebase', '--abort'], capture_output=True, silent_fail=True, cwd=str(self.root))
            pull_res = _run_git_command(['pull', '--no-edit', remote, current_branch], capture_output=True, silent_fail=True, cwd=str(self.root))

        if stashed:
            _run_git_command(['stash', 'pop'], capture_output=True, silent_fail=True, cwd=str(self.root))

        report['success'] = bool(pull_res)
        report['action_summary'] = "Sincronização aplicada com sucesso!" if pull_res else "Falha ao puxar do servidor."
        return report

    def subscribe_safe_remote(
        self,
        remote: str = 'origin',
        branch: Optional[str] = None,
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """Subscreve arquivos novos preservando modificações locais exclusivas."""
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

        self.create_safety_snapshot(reason="subscribe")
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

        self.create_safety_snapshot(reason="selective_pull")
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

        self.create_safety_snapshot(reason="force_pull_reset")
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
            except Exception as e:
                return {'success': False, 'error': str(e)}
