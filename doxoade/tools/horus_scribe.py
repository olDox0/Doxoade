# doxoade/doxoade/tools/horus_scribe.py
import ast
import sys
import os
import importlib.abc
import importlib.util

HORUS_FORBIDDEN = {
    'doxoade.tools.telemetry_tools.logger',
    'doxoade.database',
    'doxoade.tools.aegis.nexus_db',
    'doxoade.tools.horus_scribe',
    'doxoade.tools.horus',
    'doxoade.tools.doxcolors',
    'doxoade.tools.aegis.aegis_utils',
    'doxoade.tools.aegis.aegis_core',
    'doxoade.rescue',
    'doxoade.tools.vulcan.shadow_runtime',
    'doxoade.tools.aegis.shadow_scribe',
    'doxoade.tools.vulcan.shadow_scribe'
}

class HorusLoader(importlib.abc.Loader):
    def __init__(self, original_spec):
        self.spec = original_spec
        self.fullname = original_spec.name

    def exec_module(self, module):
        from doxoade.tools.aegis.aegis_core import nexus_exec
        origin = self.spec.origin
        if not origin or not os.path.exists(origin): return
        
        # Módulos vitais ou proibidos de instrumentação utilizam exec nativo diretamente.
        # Isso previne erros de importação cíclica ao carregar o próprio aegis_utils e adjacentes.
        if module.__name__ in HORUS_FORBIDDEN or "aegis_utils" in module.__name__:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                nexus_exec(f.read(), module.__dict__)
            return
            
        if self.fullname in HORUS_FORBIDDEN or "aegis_utils" in self.fullname:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
                nexus_exec(f.read(), module.__dict__)
            return
            
        try:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            module.__dict__['__file__'] = origin
            module.__dict__['__name__'] = module.__name__
            
            # Injeta referência global da função de logs operacionais
            from doxoade.tools.telemetry_tools.logger import chief_heartbeat
            module.__dict__['chief_heartbeat'] = chief_heartbeat
            
            try:
                tree = ast.parse(source)
                
                # Importação direta e instrumentação por meio do Scribe de Diamante do Vulcan
                from doxoade.tools.vulcan.shadow_scribe import NexusShadowScribe
                vax = NexusShadowScribe(os.path.basename(origin))
                vax.visit(tree)
                
                ast.fix_missing_locations(tree)
                code = compile(tree, origin, 'exec')
                
                # Executa por meio da camada segura Aegis
                from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
                restricted_safe_exec(code, module.__dict__, filename=origin, allow_imports=True)
            except Exception:
                # Fallback seguro para o caso de falha na compilação ou AST
                from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
                restricted_safe_exec(source, module.__dict__, filename=origin, allow_imports=True)
        except Exception as e:
            print(f"\x1b[31m [!] Falha Crítica no Horus Scribe ({module.__name__}): {e}\x1b[0m")

class HorusFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):s
    if fullname in HORUS_FORBIDDEN or "aegis_core" in fullname: return None
    if not (fullname.startswith("doxoade.commands") or fullname.startswith("doxoade.tools")): return None
    if any(x in fullname for x in ["telemetry", "logger", "horus", "scribe"]): return None
    for finder in sys.meta_path:
        if finder is self: continue
        try:
            spec = finder.find_spec(fullname, path, target)
            if spec and spec.origin:
                spec.loader = HorusLoader(spec) # Injeta o loader estrutural do Hórus
                return spec
        except Exception:
            pass
    return None

def activate_horus_shadow():
    if not any(isinstance(f, HorusFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, HorusFinder())