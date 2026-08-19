# doxoade/commands/lan_git/client_lan_git/lan_git_comparator.py
# Comparador de hashes de commit (Local vs Remoto)
"""
Módulo Comparador de Estado do Repositório Git Local vs Remoto.
Valida divergências de branches e suporta modo force/live.
"""

import os
import subprocess
from enum import Enum
from typing import Tuple, Optional
from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifest


class SyncStatus(Enum):
    UNINITIALIZED = "uninitialized"    
    UP_TO_DATE = "up_to_date"          
    CAN_FAST_FORWARD = "fast_forward"  
    DIVERGED = "diverged"              
    LOCAL_AHEAD = "local_ahead"        
    DIRTY_LOCAL = "dirty_local"        
    UNKNOWN = "unknown"


class LANComparator:
    """Compara o estado do Git local com o manifesto anunciado pelo peer."""

    @staticmethod
    def _run_git(repo_path: str, args: list) -> Tuple[bool, str]:
        try:
            res = subprocess.run(
                ["git", "-C", repo_path] + args,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            return (res.returncode == 0), res.stdout.strip()
        except Exception as e:
            return False, str(e)

    @classmethod
    def check_local_dirty(cls, repo_path: str) -> bool:
        """
        Verifica se há alterações em arquivos VERSIONADOS (M, D, A).
        Ignora arquivos não rastreados (??) como venv/ ou arquivos novos de pesquisa.
        """
        ok, out = cls._run_git(repo_path, ["status", "--porcelain"])
        if not ok or not out.strip():
            return False

        for line in out.splitlines():
            status_code = line[:2].strip()
            if status_code and status_code != "??":
                return True

        return False

    @classmethod
    def commit_exists_locally(cls, repo_path: str, commit_hash: str) -> bool:
        ok, _ = cls._run_git(repo_path, ["cat-file", "-e", f"{commit_hash}^{{commit}}"])
        return ok

    @classmethod
    def evaluate_sync(cls, repo_path: str, remote_manifest: GitManifest, force: bool = False) -> Tuple[SyncStatus, str]:
        """Avalia o relacionamento entre o repositório local e o manifesto remoto."""
        git_dir = os.path.join(repo_path, ".git")

        if not os.path.exists(git_dir):
            return SyncStatus.UNINITIALIZED, "Repositório local não inicializado. Inicializando Git via LAN..."

        # Se force estiver ativo, ignora dirty tree
        if not force and cls.check_local_dirty(repo_path):
            return SyncStatus.DIRTY_LOCAL, "Repositório local possui arquivos rastreados modificados."

        ok, local_head = cls._run_git(repo_path, ["rev-parse", "HEAD"])
        if not ok:
            return SyncStatus.CAN_FAST_FORWARD, "Repositório sem commits locais. Sincronizando com o Host..."

        if local_head == remote_manifest.head_commit:
            return SyncStatus.UP_TO_DATE, "O repositório local já está perfeitamente sincronizado com o peer."

        if cls.commit_exists_locally(repo_path, remote_manifest.head_commit):
            ok, _ = cls._run_git(repo_path, ["merge-base", "--is-ancestor", remote_manifest.head_commit, "HEAD"])
            if ok:
                return SyncStatus.LOCAL_AHEAD, "O repositório local possui commits mais recentes que o peer remoto."

        return SyncStatus.CAN_FAST_FORWARD, f"Atualização disponível: [{remote_manifest.short_commit}] {remote_manifest.commit_message}"