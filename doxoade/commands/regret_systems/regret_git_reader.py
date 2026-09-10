# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_git_reader.py
# Leitor de estados e diffs do Git (working tree / commits)
""" 📖 Leitor e Extrator de Estados Diferenciais do Git para Análise de Regressão.
Extrai snapshots históricos (HEAD~N), diffs de working tree (uncommitted/staged)
e identifica arquivos modificados mesmo durante operações de rebase ou detached HEAD. """

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class RegretGitReader:
    """Interface segura de extração de artefatos e diffs do Git."""

    @staticmethod
    def is_git_repository(target_path: Optional[Path] = None) -> bool:
        """Verifica se o diretório alvo pertence a um repositório Git."""
        cwd = target_path or Path.cwd()
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            return False

    @staticmethod
    def get_repo_root(target_path: Optional[Path] = None) -> Path:
        """Obtém a raiz absoluta do repositório Git."""
        cwd = target_path or Path.cwd()
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return Path(res.stdout.strip())
        except Exception:
            pass
        return cwd

    @classmethod
    def resolve_best_base_revision(cls, requested_base: Optional[str] = None, commits_back: int = 1) -> str:
        """
        Determina a melhor revisão base para comparação.
        Se estiver em rebase ou editando commit, busca o ancestral estável mais próximo.
        """
        if requested_base:
            return requested_base

        root = cls.get_repo_root()
        
        # 1. Se estiver em rebase interativo, tenta ORIG_HEAD
        try:
            res_rebase = subprocess.run(
                ["git", "rev-parse", "--verify", "ORIG_HEAD"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res_rebase.returncode == 0 and res_rebase.stdout.strip():
                return "ORIG_HEAD"
        except Exception:
            pass

        # 2. Testa HEAD~N
        candidate = f"HEAD~{commits_back}" if commits_back > 0 else "HEAD"
        try:
            res_test = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res_test.returncode == 0:
                return candidate
        except Exception:
            pass

        return "HEAD"

    @classmethod
    def get_uncommitted_files(cls) -> List[Path]:
        """Retorna lista de arquivos modificados na working tree (staged e unstaged)."""
        root = cls.get_repo_root()
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            files: List[Path] = []
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if len(line) > 3:
                        status_flag = line[:2].strip()
                        raw_file = line[3:].strip().strip('"')
                        if "D" not in status_flag:
                            p = root / raw_file
                            if p.exists() and p.is_file():
                                files.append(p)
            return files
        except Exception:
            return []

    @classmethod
    def get_file_content_at_revision(
        cls, file_path: Path, revision: str = "HEAD"
    ) -> Optional[str]:
        """Extrai o conteúdo de um arquivo em uma revisão específica do Git."""
        root = cls.get_repo_root(file_path.parent)
        try:
            rel_path = file_path.relative_to(root).as_posix()
        except ValueError:
            rel_path = file_path.as_posix()

        try:
            res = subprocess.run(
                ["git", "show", f"{revision}:{rel_path}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode == 0:
                return res.stdout
            return None
        except Exception:
            return None

    @classmethod
    def get_raw_diff(cls, file_path: Path, base_revision: str = "HEAD") -> str:
        """Obtém o diff unificado entre a versão da revisão e o arquivo atual no disco."""
        root = cls.get_repo_root(file_path.parent)
        try:
            rel_path = file_path.relative_to(root).as_posix()
        except ValueError:
            rel_path = file_path.as_posix()

        try:
            res = subprocess.run(
                ["git", "diff", base_revision, "--", rel_path],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""
