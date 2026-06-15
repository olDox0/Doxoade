# doxoade/doxoade/commands/run_systems/run_flow.py
"""Especialista de Rastro Nexus Flow (PASC 8.5)."""
import os
import sys
import ast
import click
import traceback
from traceback import print_tb as exc_trace
from doxoade.tools.doxcolors import Fore
from ...probes import flow_runner

def execute_flow(path: str, **kwargs):
    """Orquestrador Nexus Flow com Injeção Ares Shadow."""
    from doxoade.tools.vulcan.diagnostic.soteria.python_scribe import generate_python_shadow
    from ...probes import flow_runner
    
    abs_path = os.path.abspath(path).replace('\\', '/')
    
    # 1. VACINAÇÃO ARES (Shadow Build)
    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            src = f.read()
        # Gera o código vacinado na memória (injetando sys.stderr.write)
        shadow_src = generate_python_shadow(src, os.path.basename(path))
    except Exception as e:
        click.secho(f"⚠️ [ARES] Falha na vacinação: {e}", fg='yellow')
        shadow_src = None

    # 2. DISPARO DO RASTRO (Transparência Total)
    try:
        flow_runner.run_flow_direct(path, watch_vars=kwargs.get('watch_val'))
    except Exception as e:
        import traceback
        from doxoade.rescue import activate_protocol
        # Agora o traceback existe e o Lazarus vai brilhar
        activate_protocol(traceback.format_exc(), exit_code=1)
        
class PythonShadowScribe(ast.NodeTransformer):
    """
    Vacina Python: Injeta marcos de rastro em tempo real
    sem alterar o arquivo original no disco.
    """
    def __init__(self, filename):
        self.filename = filename

    def visit_FunctionDef(self, node):
        # Injeta uma chamada para o Lazarus no início de cada função
        log_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='sys', ctx=ast.Load()),
                    attr='stderr', ctx=ast.Load()
                ),
                args=[ast.Constant(value=f"[@SOTERIA_PY@] {self.filename}:{node.lineno} | {node.name}\n")],
                keywords=[]
            )
        )
        node.body.insert(0, log_node)
        return self.generic_visit(node)

def generate_python_shadow(source_code, filename):
    tree = ast.parse(source_code)
    scribe = PythonShadowScribe(filename)
    vax_tree = scribe.visit(tree)
    ast.fix_missing_locations(vax_tree)
    return ast.unparse(vax_tree)
