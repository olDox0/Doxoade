# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_hook.py
"""
Hermes MetaPathFinder - Integração com VulcanMetaFinder.
Quando o Vulcan detectar Tier 3 (Python puro), redireciona para Hermes.

Filosofia: Não criar um finder separado, mas sim fornecer uma função
que o VulcanMetaFinder pode chamar quando detectar que não há versão C.
"""
import sys
import os
import importlib.abc
import importlib.util
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# BLACKLIST DE SEGURANÇA (Anti-Recursão Infinita)
# ═══════════════════════════════════════════════════════════════════════════════
HERMES_BLACKLIST = {
    # Módulos do próprio Hermes
    'doxoade.tools.hermes_systems',
    'doxoade.tools.hermes_systems.hermes_hook',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.hermes_systems.hermes_compress',
    'doxoade.tools.hermes_systems.hermes_scanner',
    'doxoade.tools.hermes_systems.hermes_dict',
    'doxoade.tools.hermes_systems.hermes_dict.hermes_builder',
    
    # Módulos de infraestrutura crítica
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.filesystem',
    'doxoade.core_database',
    'doxoade.boot',
    'doxoade.rescue',
    'doxoade.__main__',
    'doxoade.tools.doxcolors',
    'doxoade.tools.error_info',
    
    # Módulos do Vulcan e Shadow
    'doxoade.tools.vulcan',
    'doxoade.tools.horus',
    'doxoade.tools.horus_scribe',
}

HERMES_BLACKLIST_PREFIXES = (
    'doxoade.tools.hermes_systems',
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.vulcan',
    'doxoade.tools.horus',
)

_HERMES_FINDER_MARKER = True


def _is_blacklisted(fullname: str) -> bool:
    """Verifica se um módulo está na blacklist."""
    if fullname in HERMES_BLACKLIST:
        return True
    if any(fullname.startswith(prefix) for prefix in HERMES_BLACKLIST_PREFIXES):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# HERMES LOADER (Executa o código descomprimido)
# ═══════════════════════════════════════════════════════════════════════════════
class HermesModuleLoader(importlib.abc.Loader):
    """
    Loader que descomprime o .hermes em RAM e executa.
    """
    
    def __init__(self, hermes_path: Path, dict_path: Path, original_py_path: Path = None):
        self.hermes_path = hermes_path
        self.dict_path = dict_path
        self.original_py_path = original_py_path
    
    def create_module(self, spec):
        """Cria um módulo vazio."""
        return None
    
    def exec_module(self, module):
        """
        Descomprime o .hermes e executa no namespace do módulo.
        """
        try:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            
            project_root = self.dict_path.parent.parent
            loader = HermesLoader(str(project_root))
            
            python_code = loader.decompress_file(self.hermes_path)
            module.__file__ = str(self.hermes_path)
            
            code = compile(python_code, str(self.hermes_path), 'exec')
            exec(code, module.__dict__)
            
        except Exception as e:
            if self.original_py_path and self.original_py_path.exists():
                try:
                    with open(self.original_py_path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    code = compile(source, str(self.original_py_path), 'exec')
                    module.__file__ = str(self.original_py_path)
                    exec(code, module.__dict__)
                except Exception as fallback_error:
                    raise ImportError(
                        f"Hermes fallback failed for {module.__name__}: "
                        f"Original error: {e}, Fallback error: {fallback_error}"
                    ) from fallback_error
            else:
                raise ImportError(
                    f"Hermes loader failed for {module.__name__}: {e}"
                ) from e


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO DE INTEGRAÇÃO COM VULCAN
# ═══════════════════════════════════════════════════════════════════════════════
def try_load_from_hermes(fullname: str, project_root: str):
    """
    Tenta carregar um módulo do Hermes.
    Retorna um ModuleSpec se encontrar, None caso contrário.
    
    Esta função é chamada pelo VulcanMetaFinder quando detecta Tier 3.
    """
    if _is_blacklisted(fullname):
        return None
    
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
    
    try:
        loader = HermesLoader(project_root)
    except FileNotFoundError:
        return None
    
    hermes_path = loader.find_hermes_for_module(fullname)
    if not hermes_path:
        return None
    
    # Verifica se o .py original existe (para fallback)
    parts = fullname.split('.')
    py_rel_path = Path(*parts).with_suffix('.py')
    py_path = Path(project_root) / py_rel_path
    
    # Verifica se o .hermes é mais recente que o .py
    if py_path.exists():
        hermes_mtime = hermes_path.stat().st_mtime
        py_mtime = py_path.stat().st_mtime
        if py_mtime > hermes_mtime:
            return None
    
    # Cria o ModuleSpec com o HermesLoader
    dict_path = Path(project_root) / '.doxoade' / 'hermes' / 'master.dict'
    module_loader = HermesModuleLoader(hermes_path, dict_path, py_path)
    spec = importlib.util.spec_from_loader(fullname, module_loader, origin=str(hermes_path))
    
    return spec


def install(project_root: str):
    """
    Instala o HermesFinder no sys.meta_path.
    Deve ser chamada após VulcanMetaFinder.
    """
    for finder in sys.meta_path:
        if getattr(finder, '_HERMES_FINDER_MARKER', False):
            return
    
    hermes_finder = HermesFinder(project_root)
    sys.meta_path.append(hermes_finder)
    
    if os.environ.get('VULCAN_VERBOSE') == '1':
        print(f"\x1b[90m[HERMES] MetaPathFinder instalado no sys.meta_path[{len(sys.meta_path)-1}]\x1b[0m")


def uninstall():
    """Remove o HermesFinder do sys.meta_path."""
    sys.meta_path[:] = [
        f for f in sys.meta_path 
        if not getattr(f, '_HERMES_FINDER_MARKER', False)
    ]


class HermesFinder(importlib.abc.MetaPathFinder):
    """
    MetaPathFinder que intercepta imports e procura por .hermes.
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.dict_path = self.project_root / '.doxoade' / 'hermes' / 'master.dict'
    
    def find_spec(self, fullname, path, target=None):
        """
        Procura por um módulo .hermes correspondente ao fullname.
        """
        return try_load_from_hermes(fullname, str(self.project_root))