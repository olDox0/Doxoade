import sys
import os
import ast
import importlib.abc
import importlib.machinery
from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe

class ShadowFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        # Só intercepta módulos do projeto alvo (evita quebrar bibliotecas padrão)
        if not fullname.startswith('doxoade') and not os.environ.get('SHADOW_ALL'):
            return None
            
        # Localiza o arquivo .py real
        origin = importlib.machinery.PathFinder.find_spec(fullname, path)
        if origin and origin.origin and origin.origin.endswith('.py'):
            origin.loader = ShadowLoader(fullname, origin.origin)
            return origin
        return None

class ShadowLoader(importlib.abc.Loader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def exec_module(self, module):
        from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
        with open(self.path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        
        # Vacinação AST
        tree = ast.parse(source)
        vax = NexusShadowScribe(os.path.basename(self.path))
        vax.visit(tree)
        ast.fix_missing_locations(tree)
        
        # Compilação em RAM
        code = compile(tree, self.path, 'exec')
        
        # Injeta dependências globais de segurança no módulo
        from doxoade.tools.telemetry_tools.logger import chief_heartbeat
        module.__dict__['chief_heartbeat'] = chief_heartbeat
        
        restricted_safe_exec(code, module.__dict__)