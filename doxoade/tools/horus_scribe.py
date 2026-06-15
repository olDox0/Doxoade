# doxoade/tools/horus_scribe.py
import ast
import sys
import os
import importlib.abc
import importlib.util
from .telemetry_tools.logger import chief_heartbeat

# Módulos vitais que o Horus NÃO deve tocar para evitar recursão infinita
HORUS_FORBIDDEN = {
    'doxoade.tools.telemetry_tools.logger',
    'doxoade.database',
    'doxoade.tools.aegis.nexus_db',
    'doxoade.tools.horus_scribe',
    'doxoade.tools.horus',
    'doxoade.tools.doxcolors',
    'doxoade.tools.aegis.aegis_utils', # <-- Adicionado
    'doxoade.rescue',                  # <-- Adicionado
    'doxoade.tools.vulcan.shadow_runtime',
    'doxoade.tools.aegis.shadow_scribe'
}

class HorusTransformer(ast.NodeTransformer):
    def __init__(self, mod_name):
        self.mod_name = mod_name

    def visit_FunctionDef(self, node):
        if node.name.startswith('_') or node.name in ['chief_heartbeat', 'horus_trace']:
            return node

        func_id = f"{self.mod_name}.{node.name}"
        
        # 1. Rastro de Entrada
        in_msg = f"chief_heartbeat('SHADOW', 'ENTER', {{'f': '{func_id}', 'file': '{self.mod_name}'}})"
        
        # 2. Lógica de Captura de Saída e Vácuo
        # Injetamos um rastro que tenta analisar o resultado antes do 'finally'
        # Nota: Para capturar o retorno real, precisaríamos de um transformer de 'Return'
        # Por enquanto, focamos no rastro de encerramento
        out_msg = f"""
try:
    # Registra a saída. Se estendermos para capturar 'return', o dado vai aqui.
    chief_heartbeat('SHADOW', 'EXIT', {{'f': '{func_id}', 'status': 'COMPLETE'}})
except: pass
"""
        
        # 3. Cirurgia AST: Envolvemos o corpo original
        node.body = [
            ast.parse(in_msg).body[0],
            ast.Try(
                body=node.body,
                handlers=[], orelse=[],
                finalbody=ast.parse(out_msg).body
            )
        ]
        return node

class HorusLoader(importlib.abc.Loader):
    def __init__(self, original_spec):
        self.spec = original_spec
        self.fullname = original_spec.name

    def exec_module(self, module):
        origin = self.spec.origin
        if not origin or not os.path.exists(origin): return

        # 1. TRATAMENTO DE INFRAESTRUTURA (ZONA SAGRADA)
        # Se for um módulo proibido, carregamos via nexus_exec sem vacinação

        if module.__name__ in HORUS_FORBIDDEN or "aegis_utils" in module.__name__:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                # --- TROCA TÁTICA: exec -> nexus_exec ---
                from doxoade.tools.aegis.aegis_core import nexus_exec
                nexus_exec(f.read(), module.__dict__)
            return

        if self.fullname in HORUS_FORBIDDEN or "aegis_utils" in self.fullname:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
                try:
                    from doxoade.tools.aegis.aegis_core import nexus_exec
                    nexus_exec(source_code, module.__dict__)
                except ImportError:
                    # Fallback extremo apenas se o aegis_core ainda não existir
                    exec(source_code, module.__dict__) 
            return

        # 2. TRATAMENTO DE COMANDOS E TOOLS (VACINAÇÃO)
        try:
            with open(origin, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            module.__dict__['__file__'] = origin
            module.__dict__['__name__'] = module.__name__
            
            try:
                from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
                tree = ast.parse(source)
                vax = NexusShadowScribe(os.path.basename(origin))
                vax.visit(tree)
                ast.fix_missing_locations(tree)
                code = compile(tree, origin, 'exec')
                
                from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
                restricted_safe_exec(code, module.__dict__)
            except Exception:
                from doxoade.tools.aegis.aegis_core import nexus_exec
                nexus_exec(source, module.__dict__)
        except Exception as e:
            print(f"\x1b[31m [!] Falha Crítica no Horus Scribe ({module.__name__}): {e}\x1b[0m")

class HorusFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in HORUS_FORBIDDEN:
            return None
            
        if not (fullname.startswith("doxoade.commands") or fullname.startswith("doxoade.tools")):
            return None
        
        # Prevenção extra de recursão
        if any(x in fullname for x in ["telemetry", "logger", "horus", "scribe"]):
            return None

        for finder in sys.meta_path:
            if finder is self: continue
            try:
                spec = finder.find_spec(fullname, path, target)
                if spec and spec.origin and spec.origin.endswith('.py'):
                    spec.loader = HorusLoader(spec)
                    return spec
            except: continue
        return None

def activate_horus_shadow():
    if not any(isinstance(f, HorusFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, HorusFinder())