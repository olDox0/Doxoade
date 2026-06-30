# doxoade/doxoade/tools/vulcan/shadow_runtime.py
import os
import sys
import ast
import json
import importlib.abc
import importlib.util
import importlib.machinery
# [DOX-UNUSED] from pathlib import Path

# [DOX-UNUSED] from doxoade.tools.aegis.aegis_core import nexus_exec

try:
    pass  # [DOX-UNUSED] from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
except Exception as e:
    import sys as exc_sys
    from traceback import print_tb as exc_trace
    _, exc_obj, exc_tb = exc_sys.exc_info()
    exc_trace(exc_tb)
    from doxoade.rescue import activate_protocol
    import traceback
    activate_protocol(traceback.format_exc())
    
 #   from .shadow_scribe import NexusShadowScribe

SHADOW_BLACKLIST = {
    'doxoade.tools.aegis',
#    'doxoade.tools.aegis.nexus_db',
#    'doxoade.tools.aegis.aegis_utils',
    'doxoade.tools.vulcan',
#    'doxoade.tools.vulcan.shadow_runtime',
#    'doxoade.tools.vulcan.shadow_scribe',
#    'doxoade.tools.vulcan.bridge',
    'doxoade.tools.telemetry_tools',
#    'doxoade.tools.telemetry_tools.logger',
    'doxoade.tools.horus_scribe',
    'doxoade.rescue',
    'doxoade.database',
    'doxoade.tools.filesystem',
    'toml', 'ast', 'inspect',
    'json', 'shutil', 'importlib',
    'click.core', 'click.decorators', 'click.globals', 'click.formatting',
}

_INSTALLED = False
_INSTALLED_SHADOW = False

def is_shadow_enabled(project_root: str) -> bool:
    """Detecta se o Shadow Runtime deve ser ativado (Env > TOML > Default)."""
    env_val = os.environ.get('DOXOADE_SHADOW')
    if env_val is not None:
        return env_val == '1'
    try:
        import toml
        toml_path = os.path.join(project_root, 'pyproject.toml')
        if os.path.exists(toml_path):
            config = toml.load(toml_path)
            return config.get('tool', {}).get('doxoade', {}).get('shadow_runtime', True)
    except Exception:
        pass
    return True

class ASTEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ast.AST):
            return ast.dump(obj)
        if isinstance(obj, type):
            return obj.__name__  # ✅ Corrigido: __name__ em vez de name
        # Adiciona suporte para objetos genéricos
        if hasattr(obj, '__dict__'):
            return str(obj)  # Converte para string representacional
        return super().default(obj)

class ShadowFinder(importlib.abc.MetaPathFinder):
    def __init__(self, project_root):
        self.project_root = project_root
        self._in_progress = set()

    def find_spec(self, fullname, path, target=None):
        if fullname.startswith('doxoade.tools'):
            return None
        if not (fullname.startswith('doxoade.commands') or fullname.startswith('doxoade.API')):
            if not fullname.startswith('doxoade'):
                pass
            else:
                return None
        if fullname in SHADOW_BLACKLIST or fullname in self._in_progress:
            return None
        if not (fullname.startswith('doxoade') or fullname.startswith('commands')):
            return None
        self._in_progress.add(fullname)
        try:
            origin = importlib.machinery.PathFinder.find_spec(fullname, path)
            if origin and origin.origin and origin.origin.endswith('.py'):
                origin.loader = ShadowLoader(fullname, origin.origin)
                return origin
        finally:
            self._in_progress.remove(fullname)
        return None

class ShadowLoader(importlib.abc.Loader):
    def __init__(self, fullname, path):
        self.fullname, self.path = fullname, path

    def exec_module(self, module):
        from doxoade.tools.aegis.aegis_core import nexus_exec
        with open(self.path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        module.__dict__.update({
            '__file__': self.path, '__name__': self.fullname,
            '__package__': self.fullname.rpartition('.')[0],
            '__builtins__': __builtins__
        })
        try:
            tree = ast.parse(source, filename=self.path)
            from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
            vax = NexusShadowScribe(os.path.basename(self.path))
            vax.visit(tree)
            ast.fix_missing_locations(tree)
            code = compile(tree, self.path, 'exec')
            from doxoade.tools.telemetry_tools.logger import chief_heartbeat
            module.__dict__['chief_heartbeat'] = chief_heartbeat
            
            # Correção Aegis Self-Block: Usar o built-in exec para módulos internos e confiáveis
            # do próprio sistema do Doxoade, prevenindo falsos positivos de sandbox.
            os.environ['DOXOADE_AUTHORIZED_RUN'] = '1' 
            try:
                nexus_exec(code, module.__dict__)
            finally:
                os.environ['DOXOADE_AUTHORIZED_RUN'] = '0' 
        except Exception:
            os.environ['DOXOADE_AUTHORIZED_RUN'] = '0'
            nexus_exec(source, module.__dict__)

def install_shadow_runtime(project_root):
    """Instala a INSTÂNCIA do ShadowFinder respeitando o MetaPath."""
    global _INSTALLED_SHADOW
    if _INSTALLED_SHADOW: return
    
    # Remove Apenas duplicatas do próprio Shadow
    sys.meta_path = [f for f in sys.meta_path if "ShadowFinder" not in str(f)]

    finder_instance = ShadowFinder(project_root)
    # Insere na posição 1, logo atrás do Vulcan (que estará na 0)
    pos = 1 if len(sys.meta_path) > 0 else 0
    sys.meta_path.insert(pos, finder_instance)
    _INSTALLED_SHADOW = True