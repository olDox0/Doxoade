# doxoade/dnm.py
import os
import logging 

from typing import List, Optional
from pathlib import Path
from doxoade.tools.filesystem import _get_project_config

try:
    import pathspec
except ImportError as e:
    # log e fallback: força usar versão pure-python instalada
    import importlib
    try:
        pathspec = importlib.import_module("pathspec")
    except Exception:
        raise

class DNM:
    """
    Directory Navigation Module.
    Autoridade central para rastreamento de arquivos e aplicação de regras de ignore.
    """
    
    # Ignores Universais (Nunca analisar)
    SYSTEM_IGNORES = {
        '__pycache__', '.git', '.hg', '.svn', '.tox', '.venv', 'venv', 
        'pytest_temp_dir', 'foundry', 'bin', 'recovery_zone', 'tmp',
        'env', 'node_modules', '.idea', '.vscode', '.doxoade_cache', 
        'dist', 'build', 'doxoade.egg-info', 'htmlcov', '.pytest_cache'
    }
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.ignore_spec = self._load_ignore_spec()
    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Carrega regras de ignore com fallback para Modo Genérico."""
        patterns = list(self.SYSTEM_IGNORES)
        
        try:
            # 1. Tenta carregar do TOML (se existir)
            config = _get_project_config(None, start_path=str(self.root))
            toml_ignores = config.get('ignore', [])
            patterns.extend(toml_ignores)
        except Exception: pass
        # 2. Tenta carregar do .gitignore (se existir)
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            try:
                with open(gitignore, "r", encoding="utf-8") as f:
                    patterns.extend(f.read().splitlines())
            except Exception: pass
        # Se a lista estiver vazia (além do sistema), adiciona o básico
        if len(patterns) == len(self.SYSTEM_IGNORES):
            patterns.append("*.pyc")
            patterns.append("__pycache__/")
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    def is_ignored(self, file_path) -> bool:
        try:
            abs_p = os.path.abspath(file_path).replace('\\', '/')
            if any(x in abs_p for x in ['nppBackup', '.bak', 'pytest_temp_dir']):
                return True
            
            rel_p = os.path.relpath(abs_p, self.root).replace('\\', '/')
            
            # FIX: Sincronizado com rel_p
            for part in rel_p.split('/'):
                if part in self.SYSTEM_IGNORES:
                    return True
            return self.ignore_spec.match_file(rel_p)
        except Exception as e:
            logging.info(f" is_ignored - Exception: {e}")
            return False
        # Verifica se alguma parte do caminho é proibida explicitamente
        for part in rel_p.parts:
            if part in self.SYSTEM_IGNORES:
                return True
        # Normaliza para comparação com pathspec
        return self.ignore_spec.match_file(str(rel_p).replace(os.sep, "/"))
    def scan(self, extensions: Optional[List[str]] = None) -> List[str]:
        valid_files = []
        if extensions:
            extensions = {e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions}
        for root, dirs, files in os.walk(str(self.root)):
            root_path = Path(root)
            
            # Filtro de Pastas (Performance)
            dirs[:] = [d for d in dirs if not self.is_ignored(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                if extensions and file_path.suffix.lower() not in extensions:
                    continue
                
                if self.is_ignored(file_path):
                    continue
                
                # PADRONIZAÇÃO GOLD: Absoluto + Unix Style
                # Isso evita que o Windows quebre a comparação de strings nas sondas
                canonical_path = str(file_path.absolute()).replace('\\', '/')
                valid_files.append(canonical_path)
        return sorted(valid_files)
        
# No final do arquivo doxoade/dnm.py
try:
    from .tools.vulcan.bridge import vulcan_bridge
    vulcan_bridge.apply_turbo("dnm", globals())
except Exception as e:
    import sys as dox_exc_sys
    _, exc_obj, exc_tb = dox_exc_sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    line_number = exc_tb.tb_lineno
    print(f"\033[0m \033[1m Filename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \033[0m")