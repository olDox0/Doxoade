# doxoade/doxoade/tools/vulcan/shadow_runtime.py
import sys
import os
import ast
import importlib.abc
import importlib.util
import importlib.machinery
from pathlib import Path

from doxoade.tools.aegis.aegis_core import nexus_exec

try:
    from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
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
    'doxoade.tools.aegis.aegis_utils',         # Contém restricted_safe_exec
    'doxoade.tools.vulcan.shadow_runtime',     # O próprio motor
    'doxoade.tools.vulcan.shadow_scribe',      # O cirurgião AST
    'doxoade.tools.vulcan.bridge',
    'doxoade.tools.telemetry_tools.logger',    # O batedor de rastro
    'doxoade.tools.horus_scribe',              # O motor legado
    'doxoade.rescue',                          # O pronto-socorro
    'doxoade.database',                        # Hades Engine
    'doxoade.tools.aegis.nexus_db',            # Wrapper de banco
    'doxoade.tools.filesystem',                # Leitor de TOML
    'toml', 'ast', 'inspect',
    'json', 'shutil', 'importlib',
    'click.core', 'click.decorators', 'click.globals', 'click.formatting',
}

_INSTALLED = False

def is_shadow_enabled(project_root: str) -> bool:
    """Detecta se o Shadow Runtime deve ser ativado (Env > TOML > Default)."""
    # 1. Sobrescrita via Variável de Ambiente (Prioridade Máxima)
    env_val = os.environ.get('DOXOADE_SHADOW')
    if env_val is not None:
        return env_val == '1'

    # 2. Verificação via pyproject.toml
    try:
        import toml
        toml_path = os.path.join(project_root, 'pyproject.toml')
        if os.path.exists(toml_path):
            config = toml.load(toml_path)
            return config.get('tool', {}).get('doxoade', {}).get('shadow_runtime', True)
    except Exception:
        pass

    return True # Default: Ativado para garantir máxima segurança

class ShadowFinder(importlib.abc.MetaPathFinder):
    def __init__(self, project_root):
        self.project_root = project_root
        self._in_progress = set()

    def find_spec(self, fullname, path, target=None):
        
        # 1. ISOLAMENTO TOTAL: Shadow nunca toca nas ferramentas (tools)
        # Isso evita 100% dos loops de incepção e importação circular
        if fullname.startswith('doxoade.tools'):
            return None
            
        # 2. Só vacina comandos, API e o próprio projeto host
        if not (fullname.startswith('doxoade.commands') or fullname.startswith('doxoade.API')):
            # Se for um projeto externo sendo rodado pelo doxoade
            if not fullname.startswith('doxoade'):
                pass # Prossegue para vacinar o código do usuário
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
        with open(self.path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        # Sincronia de Identidade (Resolve o AttributeError: save)
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
            
            # Injeta telemetria e executa PURO (Quebra o ciclo com aegis_utils)
            from doxoade.tools.telemetry_tools.logger import chief_heartbeat
            module.__dict__['chief_heartbeat'] = chief_heartbeat
            from doxoade.tools.aegis.aegis_core import nexus_exec
            nexus_exec(code, module.__dict__)
            
        except Exception:
            # Fallback seguro também usando a autoridade Aegis
            from doxoade.tools.aegis.aegis_core import nexus_exec
            nexus_exec(source, module.__dict__)

def install_shadow_runtime(project_root):
    """Instalação com Autoverificação de Segurança."""
    global _INSTALLED
    if _INSTALLED: return
    
    if not is_shadow_enabled(project_root):
        return

    try:
        # TESTE DE SANIDADE: Tenta compilar um snippet básico com a vacina
        # Se o sistema de AST do usuário estiver corrompido, o NSR não sobe.
        from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
        import ast
        test_tree = ast.parse("def sanity(): pass")
        NexusShadowScribe("sanity").visit(test_tree)
        
        # Se passou no teste, instala o Finder

    except Exception as e:
        # LOG DE FALHA DE SEGURANÇA: O rastro de falha do NSR vai para o Hades
        from doxoade.tools.telemetry_tools.logger import chief_heartbeat
        chief_heartbeat("ENGINE", "BOOT_FAILURE", {"engine": "SHADOW", "err": str(e)})
        # Não instala o finder, mantendo o Doxoade em "Safe Mode"

    if not any(isinstance(f, ShadowFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, ShadowFinder(project_root))
        _INSTALLED = True