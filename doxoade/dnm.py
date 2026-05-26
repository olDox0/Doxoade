# doxoade/doxoade/dnm.py
import os
import logging

from typing import List, Optional
from pathlib import Path

from doxoade.commands.doxcolors_systems.colors_command import config

from doxoade.tools.filesystem import is_ignored as central_is_ignored
from doxoade.tools.filesystem import _get_project_config

try:
    import pathspec
except ImportError: # Fallback seguro para quando a lib não está instalada
    pathspec = None
    logging.warning("Módulo 'pathspec' não encontrado. O DNM usará filtragem simplificada.")
    import importlib
    try:
        pathspec = importlib.import_module('pathspec')
    except Exception as e:
        import traceback
        print(f'\x1b[31m ■ Erro: {e}')
        traceback.print_tb(e.__traceback__)
        raise
try:
    import msvcrt # Exemplo
except ImportError:
    msvcrt = None # Mock para Linux

class DNM:
    """
    Directory Navigation Module.
    Autoridade central para rastreamento de arquivos e aplicação de regras de ignore.
    """
    SYSTEM_IGNORES = {
        '__pycache__', '.git', '.hg', '.svn', '.tox', '.venv',
        'venv', 'pytest_temp_dir', 'recovery_zone',
        'tmp', 'env', 'node_modules', '.idea', '.vscode',
        'dist', 'build', 'doxoade.egg-info', 'htmlcov', '.pytest_cache',
        'thirdparty', 'nppBackup'
    }
    FORGE_JUNK = {
        'foundry', 'opt_py', 'staging', 'lib_bin', 
        '.doxoade_cache', 'c_lang_build', 'obj'
    }
    def __init__(self, root_path: str='.'):
        self.root = Path(root_path).resolve()
        self.ignore_spec = self._load_ignore_spec()

    def _load_ignore_spec(self) -> Optional[pathspec.PathSpec]:
#    def _load_ignore_spec(self) -> pathspec.PathSpec:
        """Carrega regras de ignore com fallback para Modo Genérico."""
        patterns = list(self.SYSTEM_IGNORES)
        try:
            config = _get_project_config(None, start_path=str(self.root))
            toml_ignores = config.get('ignore', [])
            patterns.extend(toml_ignores)
        except Exception:
            pass
        gitignore = self.root / '.gitignore'
        if gitignore.exists():
            try:
                with open(gitignore, 'r', encoding='utf-8') as f:
                    patterns.extend(f.read().splitlines())
            except Exception:
                pass
        if len(patterns) == len(self.SYSTEM_IGNORES):
            patterns.append('*.pyc')
            patterns.append('__pycache__/')
        if pathspec is None:
            return None
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def is_ignored(self, file_path) -> bool:
        abs_p = os.path.abspath(file_path).replace('\\', '/')
        
        # 1. Filtro de Pastas de Fundição (Vulcan Junk)
        # Se qualquer parte do caminho estiver na lista de lixo, ignora.
        path_parts = set(abs_p.lower().split('/'))
        if not path_parts.isdisjoint(self.FORGE_JUNK):
            return True

        # 2. Filtro de Segurança Aegis (Backups e temporários)
        if any(x in abs_p for x in ['nppBackup', '.bak', 'pytest_temp_dir']):
            return True
            
        # 3. Filtro Central (SYSTEM_IGNORES e pyproject.toml)
        if central_is_ignored(abs_p, str(self.root)):
            return True
            
        return False

    def scan(self, extensions: Optional[List[str]]=None, include_internal: bool = False) -> List[str]:
        valid_files = []
        # Normaliza extensões
        if extensions:
            extensions = {e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions}
            
        for root, dirs, files in os.walk(str(self.root)):
            # PODA AGRESSIVA DE DIRETÓRIOS (Chief-Gold Optimization)
            # Isso impede que o os.walk sequer entre nas pastas proibidas
            dirs[:] = [d for d in dirs if d.lower() not in self.FORGE_JUNK and not self.is_ignored(Path(root) / d)]
#            dirs[:] = [d for d in dirs if not self.is_ignored(Path(root) / d)]

            for file in files:
                file_path = Path(root) / file
                
                # Verifica extensão
                if extensions and file_path.suffix.lower() not in extensions:
                    continue
                
                # Filtro final de arquivo
                if self.is_ignored(file_path) and not include_internal:
                    continue
                    
                canonical_path = str(file_path.absolute()).replace('\\', '/')
                valid_files.append(canonical_path)
                
        return sorted(valid_files)

try:
    from doxoade.tools.vulcan.bridge import vulcan_bridge
    vulcan_bridge.apply_turbo('dnm', globals())
except Exception as e:
    import sys as dox_exc_sys
    _, exc_obj, exc_tb = dox_exc_sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    line_number = exc_tb.tb_lineno
    print(f'\x1b[0m \x1b[1m Filename: {fname}   ■ Line: {line_number} \x1b[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \x1b[0m')
