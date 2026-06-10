# doxoade/doxoade/tools/horus_scribe.py
import ast
import sys
import os
import importlib.abc
import importlib.util
from .telemetry_tools.logger import chief_heartbeat
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec

# Módulos vitais que o Horus NÃO deve tocar para evitar recursão infinita
HORUS_FORBIDDEN = {
    'doxoade.tools.telemetry_tools.logger',
    'doxoade.database',
    'doxoade.tools.aegis.nexus_db',
    'doxoade.tools.horus_scribe',
    'doxoade.tools.horus',
    'doxoade.tools.doxcolors'
    'doxoade.tools.telemetry_tools.logger', 'doxoade.database',
    'doxoade.tools.aegis.nexus_db', 'doxoade.tools.horus_scribe',
    'doxoade.tools.horus', 'doxoade.tools.doxcolors'
}

class HorusTransformer(ast.NodeTransformer):
    def __init__(self, mod_name):
        self.mod_name = mod_name

    def visit_FunctionDef(self, node):
        if node.name.startswith('_') or node.name in ['chief_heartbeat', 'horus_trace']:
            return node

        func_id = f"{self.mod_name}.{node.name}"
        
        # [PLATINUM] Injeção Minimalista e Segura
        in_msg = f"chief_heartbeat('HORUS', 'FUNCTION_IN', {{'func': '{func_id}'}})"
        out_msg = f"chief_heartbeat('HORUS', 'FUNCTION_OUT', {{'func': '{func_id}'}})"
        err_msg = f"chief_heartbeat('HORUS', 'FUNCTION_ERROR', {{'func': '{func_id}', 'error': str(e)}})"

        # Envolvemos o código original mantendo a integridade do retorno
        new_body = [
            ast.parse(in_msg).body[0],
            ast.Try(
                body=node.body,
                handlers=[ast.ExceptHandler(
                    type=ast.Name(id='Exception', ctx=ast.Load()), name='e',
                    body=[ast.parse(err_msg).body[0], ast.Raise()]
                )],
                orelse=[],
                finalbody=[ast.parse(out_msg).body[0]]
            )
        ]
        node.body = new_body
        return node

class HorusLoader(importlib.abc.Loader):
    def __init__(self, original_spec):
        self.spec = original_spec

    def exec_module(self, module):
        # [FIX] Segurança contra NoneType (módulos sem arquivo)
        if not self.spec.origin or not os.path.exists(self.spec.origin):
            return
            
        try:
            with open(self.spec.origin, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
            vax = HorusTransformer(module.__name__)
            vax.visit(tree)
            ast.fix_missing_locations(tree)
            
            code = compile(tree, self.spec.origin, 'exec')
            # Garante que o logger esteja acessível para a injeção
            module.__dict__['chief_heartbeat'] = chief_heartbeat
            restricted_safe_exec(code, module.__dict__)
        except Exception:
            # Fallback total: se a vacina falhar, carrega o original limpo
            with open(self.spec.origin, 'r', encoding='utf-8', errors='ignore') as f:
                restricted_safe_exec(f.read(), module.__dict__)

class HorusFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not (fullname.startswith("doxoade.tools") or fullname.startswith("doxoade.commands")):
            return None
        if fullname in HORUS_FORBIDDEN:
            return None

        for finder in sys.meta_path:
            if finder is self: continue
            try:
                spec = finder.find_spec(fullname, path, target)
                # [FIX] Só vacina se for um arquivo Python físico
                if spec and spec.origin and spec.origin.endswith('.py'):
                    spec.loader = HorusLoader(spec)
                    return spec
            except: continue
        return None

def activate_horus_shadow():
    sys.meta_path.insert(0, HorusFinder())