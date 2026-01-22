# -*- coding: utf-8 -*-
# doxoade/commands/deepcheck.py
import ast, os, click, json
from colorama import Fore
from .deepcheck_utils import DeepAnalyzer, _render_deep_report
from .deepcheck_io import (
    load_git_content, save_analysis_snapshot, 
    load_analysis_snapshot, render_lineage_summary
)

def _prepare_context(content): 
    tree = ast.parse(content)
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node): child.parent = node
    
    module_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name.split('.')[0] for n in (node.names if hasattr(node, 'names') else [])]
            if isinstance(node, ast.ImportFrom) and node.module: names.append(node.module.split('.')[0])
            module_imports.update(names)

    from radon.visitors import ComplexityVisitor
    try: cc_map = {f.name: f.complexity for f in ComplexityVisitor.from_code(content).functions}
    except: cc_map = {}
    return {"tree": tree, "imports": module_imports, "cc_map": cc_map}

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--func', '-f', help="Analisa apenas esta função.")
@click.option('--variable', '-v', is_flag=True, help="Inspeção detalhada de variáveis.")
@click.option('--flow', is_flag=True, help="Visualiza o fluxo de dados.")
@click.option('--compare-json', '-cj', is_flag=True, help="Compara com snapshot local.")
@click.option('--compare-git', '-cg', default=None, help="Compara com Git (ex: HEAD).")
@click.option('--json', 'as_json', is_flag=True, help="Saída em JSON.")
def deepcheck(file_path, func, variable, flow, as_json, compare_json, compare_git):
    """🩺 Raio-X semântico e estrutural de Linhagem de Dados."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        ctx = _prepare_context(content)
        comp_map = {}

        # 1. Gerenciamento de Comparação via deepcheck_io
        if compare_git:
            git_content = load_git_content(file_path, compare_git)
            if git_content:
                g_ctx = _prepare_context(git_content)
                for node in [n for n in ast.walk(g_ctx["tree"]) if isinstance(n, ast.FunctionDef)]:
                    v = DeepAnalyzer(module_imports=g_ctx["imports"]); v.visit(node)
                    comp_map[node.name] = _render_deep_report(v, node.name, g_ctx["cc_map"].get(node.name, 1), as_json=True)
        elif compare_json:
            comp_map = load_analysis_snapshot(file_path)

        # 2. Execução da Análise
        nodes = [n for n in ast.walk(ctx["tree"]) if isinstance(n, ast.FunctionDef)]
        if func: nodes = [n for n in nodes if n.name == func]

        final_results = []
        for node in nodes:
            visitor = DeepAnalyzer(module_imports=ctx["imports"]); visitor.visit(node)
            report = _render_deep_report(
                visitor, node.name, ctx["cc_map"].get(node.name, 1), 
                as_json=as_json, show_vars=variable, show_flow=flow,
                compare_to=comp_map.get(node.name)
            )
            final_results.append(report)
            
            # Se --flow estiver ativo, renderiza o resumo executivo final
            if flow and not as_json:
                render_lineage_summary(visitor)

        # 3. Salvamento Automático (Snapshot)
        save_analysis_snapshot(file_path, final_results)

        if as_json:
            print(json.dumps(final_results, indent=2, ensure_ascii=False))

    except Exception as e:
        import sys as _dox_sys
        _, _, exc_tb = _dox_sys.exc_info()
        while exc_tb and exc_tb.tb_next: exc_tb = exc_tb.tb_next
        line = exc_tb.tb_lineno if exc_tb else 0
        click.echo(f"\033[31m[ ERROR ] {type(e).__name__} at L{line}: {e}\033[0m")