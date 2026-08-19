# doxoade/commands/lan_git/discovery_lan_git/project_resolver_lan_git.py
""" Módulo de Resolução e Descoberta de Silos e Projetos Locais para o LAN Git.
Localiza repositórios pelo nome simplificado (ex: 'sysutils') sem exigir caminhos absolutos. """

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ProjectResolver:
    """Localizador e validador inteligente de Silos/Projetos no ecossistema Doxoade."""

    # Pastas e nomes de sistema que devem ser ignorados durante a varredura
    IGNORED_DIRS = {
        "venv", ".venv", "env", "__pycache__", ".git", "build", "dist",
        "node_modules", "AppData", "Local", "Temp", "$Recycle.Bin"
    }

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normaliza o nome para casamento difuso (remove prefixos, traços e espaços)."""
        clean = name.lower()
        clean = re.sub(r"^(projeto|project)[-_\s]+", "", clean)
        clean = re.sub(r"[-_\s]+(proj|project|silo)$", "", clean)
        clean = re.sub(r"[-_\s.]+", "", clean)
        return clean.strip()

    @classmethod
    def validate_silo_integrity(cls, repo_path: str) -> Tuple[bool, Optional[str]]:
        """Verifica se o diretório é um projeto Git válido e seguro para compartilhamento."""
        if not os.path.exists(repo_path):
            return False, f"Caminho não existe: {repo_path}"

        if not os.path.isdir(repo_path):
            return False, f"O caminho não é um diretório: {repo_path}"

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir) and not repo_path.endswith(".git"):
            # Verifica se pelo menos tem arquivos de projeto (pyproject.toml/setup.py)
            has_project_file = any(
                os.path.exists(os.path.join(repo_path, f))
                for f in ("pyproject.toml", "requirements.txt", "setup.py", "install_setup.py")
            )
            if not has_project_file:
                return False, f"Diretório '{repo_path}' não é um repositório Git nem um projeto Python reconhecido."

        return True, None

    @classmethod
    def resolve_project_path(cls, project_query: str, start_path: str = ".") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Localiza o caminho absoluto de um projeto a partir de uma consulta simplificada (ex: 'sysutils').
        Retorna (sucesso: bool, caminho_absoluto: Optional[str], mensagem_erro: Optional[str]).
        """
        if not project_query or not project_query.strip():
            abs_start = os.path.abspath(start_path)
            ok, err = cls.validate_silo_integrity(abs_start)
            return ok, abs_start if ok else None, err

        query = project_query.strip()

        # 1. Tentativa Direta: O usuário passou um caminho relativo ou absoluto válido
        if os.path.exists(query) and os.path.isdir(query):
            abs_path = os.path.abspath(query)
            ok, err = cls.validate_silo_integrity(abs_path)
            if ok:
                return True, abs_path, None

        norm_query = cls._normalize_name(query)
        candidates: List[str] = []

        # 2. Varredura Hierárquica em Pastas Pais e Irmãs (Workspace Discovery)
        start_dir = Path(os.path.abspath(start_path))
        search_roots = [start_dir]

        # Sobe até 4 níveis na árvore de pastas para encontrar coleções de projetos (ex: Projetos_E_Programas, DOSSIER)
        curr = start_dir
        for _ in range(4):
            if curr.parent and curr.parent != curr:
                curr = curr.parent
                search_roots.append(curr)

        seen_paths = set()

        for root_dir in search_roots:
            try:
                for item in root_dir.iterdir():
                    if item.is_dir() and item.name not in cls.IGNORED_DIRS:
                        norm_item = cls._normalize_name(item.name)
                        item_str = str(item.resolve())

                        if item_str not in seen_paths:
                            seen_paths.add(item_str)
                            # Casamento exato ou parcial prioritário
                            if norm_item == norm_query or norm_query in norm_item:
                                ok, _ = cls.validate_silo_integrity(item_str)
                                if ok:
                                    candidates.append(item_str)
            except Exception:
                continue

        if not candidates:
            return False, None, f"Nenhum Silo/Projeto correspondente a '{project_query}' foi localizado nas pastas do workspace."

        # Prioriza o match mais próximo/curto
        candidates.sort(key=lambda p: (cls._normalize_name(os.path.basename(p)) != norm_query, len(p)))
        chosen_project = candidates[0]

        return True, chosen_project, None

    @classmethod
    def list_available_projects(cls, start_path: str = ".") -> List[Dict[str, str]]:
        """Varre o workspace e lista todos os projetos disponíveis com metadados do Git."""
        start_dir = Path(os.path.abspath(start_path))
        search_roots = [start_dir]

        curr = start_dir
        for _ in range(4):
            if curr.parent and curr.parent != curr:
                curr = curr.parent
                search_roots.append(curr)

        projects = []
        seen_paths = set()

        for root_dir in search_roots:
            try:
                for item in root_dir.iterdir():
                    if item.is_dir() and item.name not in cls.IGNORED_DIRS:
                        item_str = str(item.resolve())
                        if item_str not in seen_paths:
                            seen_paths.add(item_str)
                            git_dir = item / ".git"
                            if git_dir.exists() and git_dir.is_dir():
                                branch, commit = cls._get_git_info(item_str)
                                projects.append({
                                    "name": item.name,
                                    "path": item_str,
                                    "branch": branch,
                                    "commit": commit
                                })
            except Exception:
                continue

        projects.sort(key=lambda x: x["name"].lower())
        return projects

    @staticmethod
    def _get_git_info(repo_path: str) -> Tuple[str, str]:
        """Obtém branch e commit curto de um repositório."""
        branch = "main"
        commit = "0000000"
        try:
            res = subprocess.run(["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=3, check=False)
            if res.returncode == 0:
                branch = res.stdout.strip()
            res = subprocess.run(["git", "-C", repo_path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=3, check=False)
            if res.returncode == 0:
                commit = res.stdout.strip()
        except Exception:
            pass
        return branch, commit