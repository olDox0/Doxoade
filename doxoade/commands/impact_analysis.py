# doxoade/commands/impact_analysis.py
import os
import ast
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_project_config

def _resolve_relative_import(module_name, level, current_file_module):
    if level == 0: return module_name
    base_path = current_file_module.split('.')
    climb_from = base_path[:-1]
    ascended_path = climb_from[:-(level - 1)]
    if module_name:
        full_module = ascended_path + module_name.split('.')
    else:
        full_module = ascended_path
    return ".".join(full_module)

class DetailedAnalysisVisitor(ast.NodeVisitor):
    def __init__(self, current_module):
        self.imports = set()
        self.usages = set()
        self.defined_functions = set()
        self.current_module = current_module

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.level > 0:
            resolved = _resolve_relative_import(node.module, node.level, self.current_module)
            self.imports.add(resolved)
        elif node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.usages.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load):
            self.usages.add(node.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.defined_functions.add(node.name)
        self.generic_visit(node)

def _path_to_module_name(file_path, root_path):
    try:
        rel_path = os.path.relpath(file_path, root_path)
    except ValueError:
        rel_path = os.path.basename(file_path)
    base = os.path.splitext(rel_path)[0]
    normalized = base.replace('\\', '.').replace('/', '.')
    if normalized.startswith('.'):
        normalized = normalized[1:]
    return normalized

def _build_advanced_index(search_path, ignore_patterns, logger):
    click.echo(Fore.WHITE + "Mapeando estrutura do projeto...")
    index = {}
    
    for root, dirs, files in os.walk(search_path):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not d.startswith('.')]
        
        for file in files:
            if not file.endswith('.py'): continue
            
            file_path = os.path.join(root, file)
            module_name = _path_to_module_name(file_path, search_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if not content: continue
                    tree = ast.parse(content)
                
                visitor = DetailedAnalysisVisitor(module_name)
                visitor.visit(tree)
                
                index[module_name] = {
                    "path": os.path.relpath(file_path, search_path),
                    "imports": visitor.imports,
                    "calls": visitor.usages,
                    "defines": visitor.defined_functions
                }
            except Exception: continue
            
    return index

def _present_tracking_results(target_module, index):
    target_data = index.get(target_module)
    if not target_data: return

    defined_funcs = target_data.get("defines", set())
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- RASTREAMENTO AVANÇADO: {target_module} ---")
    
    click.echo(Fore.YELLOW + "\n[+] USO DE FUNÇÕES (Heurística):")
    
    used_funcs = set()
    for mod, data in index.items():
        if target_module in data.get("imports", set()):
            calls = data.get("calls", set())
            intersection = calls.intersection(defined_funcs)
            
            if intersection:
                path = data.get("path")
                click.echo(Fore.GREEN + f"  - Em {path}:")
                for func in intersection:
                    click.echo(Fore.WHITE + f"    > Usa: {func}")
                    used_funcs.update([func])

    unused = defined_funcs - used_funcs
    if unused:
        click.echo(Fore.RED + "\n[!] FUNÇÕES POTENCIALMENTE NÃO USADAS (Dead Code?):")
        click.echo(Fore.WHITE + f"    {', '.join(sorted(unused))}")
        click.echo(Style.DIM + "    (Nota: Pode ser falso positivo se usado dinamicamente)")

    click.echo(Fore.YELLOW + "\n[+] CHAMADAS EXTERNAS:")
    calls = target_data.get("calls", set())
    external_calls = calls - defined_funcs
    builtins = {'print', 'len', 'str', 'int', 'list', 'dict', 'set', 'open', 'range'}
    interesting_calls = external_calls - builtins
    
    if interesting_calls:
        click.echo(Fore.WHITE + f"    {', '.join(sorted(list(interesting_calls))[:15])}")
        if len(interesting_calls) > 15:
            click.echo(Fore.WHITE + f"    ... e mais {len(interesting_calls)-15}.")
    else:
        click.echo(Fore.WHITE + "    Nenhuma chamada externa relevante detectada.")

@click.command('impact-analysis')
@click.pass_context
@click.argument('file_path_arg', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True), default='.')
@click.option('--tracking', '-t', is_flag=True, help="Ativa rastreamento profundo de funções e uso.")
def impact_analysis(ctx, file_path_arg, project_path, tracking):
    """Analisa dependências e rastreia uso de código."""
    with ExecutionLogger('impact-analysis', project_path, ctx.params) as logger:
        config = _get_project_config(logger, start_path=project_path)
        search_path = config.get('search_path', '.')
        ignore_patterns = {item.strip('/\\') for item in config.get('ignore', [])}

        # Constrói índice (CORRIGIDO: usa a variável certa)
        project_index = _build_advanced_index(search_path, ignore_patterns, logger)
        
        target_module = _path_to_module_name(file_path_arg, search_path)
        
        if target_module not in project_index:
            click.echo(Fore.RED + "Arquivo não indexado (verifique .gitignore ou caminho).")
            return

        # Análise Padrão (Imports)
        # CORRIGIDO: usa 'project_index' em vez de 'index'
        data = project_index[target_module]
        inbound = data.get("imports", set())
        outbound = [idx_data["path"] for mod, idx_data in project_index.items() if target_module in idx_data.get("imports", set())]

        click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- Impacto: {target_module} ---")
        click.echo(Fore.YELLOW + f"\n[IN] Depende de ({len(inbound)}):")
        for dep in sorted(inbound): click.echo(f"  - {dep}")
        
        click.echo(Fore.YELLOW + f"\n[OUT] Usado por ({len(outbound)}):")
        for dep in sorted(outbound): click.echo(f"  - {dep}")

        # Análise Avançada (Tracking)
        if tracking:
            _present_tracking_results(target_module, project_index)