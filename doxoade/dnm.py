# doxoade/dnm.py
import os
import pathspec
from pathlib import Path
from typing import List, Optional
from doxoade.tools.filesystem import _get_project_config

class DNM:
    """
    Directory Navigation Module.
    Autoridade central para rastreamento de arquivos e aplicação de regras de ignore.
    """
    
    # Ignores Universais (Nunca analisar)
    SYSTEM_IGNORES = {
        '__pycache__', '.git', '.hg', '.svn', '.tox', '.venv', 'venv', 
        'env', 'node_modules', '.idea', '.vscode', '.doxoade_cache', 
        'dist', 'build', 'doxoade.egg-info', 'htmlcov', '.pytest_cache'
    }

    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.ignore_spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Carrega regras de ignore do TOML e padrões do sistema."""
        patterns = list(self.SYSTEM_IGNORES)
        
        # 1. Carrega do pyproject.toml
        config = _get_project_config(None, start_path=str(self.root))
        toml_ignores = config.get('ignore', [])
        patterns.extend(toml_ignores)
        
        # 2. Carrega do .gitignore (se existir) para paridade com Git
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            with open(gitignore, "r", encoding="utf-8") as f:
                patterns.extend(f.read().splitlines())

        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def is_ignored(self, file_path: Path) -> bool:
        """Verifica se um caminho (arquivo ou pasta) deve ser ignorado."""
        try:
            rel_path = file_path.relative_to(self.root)
        except ValueError:
            return True # Fora da raiz

        # Verifica se alguma parte do caminho é proibida explicitamente
        # (ex: venv/lib/site-packages -> venv é proibido)
        for part in rel_path.parts:
            if part in self.SYSTEM_IGNORES:
                return True

        # Usa a spec do gitignore/toml para match complexo
        # pathspec trabalha melhor com strings estilo unix
        return self.ignore_spec.match_file(str(rel_path).replace(os.sep, "/"))

    def scan(self, extensions: Optional[List[str]] = None) -> List[str]:
        """
        Retorna lista de caminhos ABSOLUTOS de arquivos válidos.
        """
        valid_files = []
        
        # Normaliza extensões (ex: ['.py'])
        if extensions:
            extensions = {e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions}

        for root, dirs, files in os.walk(self.root):
            root_path = Path(root)
            
            # 1. Filtragem de Diretórios (In-place modification)
            # Remove diretórios ignorados para não descer neles (Performance)
            # Precisamos iterar sobre uma cópia para modificar a lista original
            dirs[:] = [
                d for d in dirs 
                if not self.is_ignored(root_path / d)
            ]
            
            # 2. Filtragem de Arquivos
            for file in files:
                file_path = root_path / file
                
                # Filtro de Extensão
                if extensions and file_path.suffix.lower() not in extensions:
                    continue
                
                # Filtro de Ignore
                if self.is_ignored(file_path):
                    continue
                
                valid_files.append(str(file_path))

        return sorted(valid_files)