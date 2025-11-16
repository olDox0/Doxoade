# doxoade/commands/impact_analysis.py
import os
import ast
import click
#from pathlib import Path
from colorama import Fore, Style

from ..shared_tools import (
    ExecutionLogger,
    _get_project_config
)

def _path_to_module_name(file_path, root_path):
    """Converte um caminho de arquivo em um nome de módulo Python (ex: doxoade.commands.auto)."""
    rel_path = os.path.relpath(file_path, root_path)
    if rel_path.endswith('__init__.py'):
        module_path = os.path.dirname(rel_path)
    else:
        module_path = rel_path[:-3] if rel_path.endswith('.py') else rel_path
    return module_path.replace(os.sep, '.')

class ImportVisitor(ast.NodeVisitor):
    """Percorre a AST para encontrar todas as declarações de import."""
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

def _present_impact_results(inbound_deps, outbound_dependents):
    """Função de apresentação customizada para o 'impact-analysis'."""
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Análise de Impacto Concluída ---")

    # --- Seção 1: Dependências de Entrada (Inbound) ---
    click.echo(Fore.YELLOW + f"\n[+] O arquivo analisado DEPENDE de ({len(inbound_deps)}):")
    if not inbound_deps:
        click.echo(Fore.WHITE + "    Nenhum módulo importado.")
    else:
        # Separa em bibliotecas padrão/terceiros e internas do projeto
        internal_deps = sorted([dep for dep in inbound_deps if dep.startswith('doxoade')])
        external_deps = sorted([dep for dep in inbound_deps if not dep.startswith('doxoade')])
        
        if external_deps:
            click.echo(Fore.WHITE + Style.BRIGHT + "    Bibliotecas Externas/Padrão:")
            for dep in external_deps:
                click.echo(Fore.WHITE + f"      - {dep}")
        
        if internal_deps:
            click.echo(Fore.WHITE + Style.BRIGHT + "    Módulos Internos do Projeto:")
            for dep in internal_deps:
                click.echo(Fore.WHITE + f"      - {dep}")

    # --- Seção 2: Dependentes (Outbound) ---
    click.echo(Fore.YELLOW + f"\n[+] É USADO POR ({len(outbound_dependents)}):")
    if not outbound_dependents:
        click.echo(Fore.WHITE + "    Nenhum outro arquivo no projeto parece importar este módulo.")
    else:
        for dep in sorted(outbound_dependents):
            click.echo(Fore.GREEN + f"    - {dep}")
    
    click.echo(Fore.CYAN + Style.BRIGHT + "--------------------------------------")


@click.command('impact-analysis')
@click.pass_context
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
def impact_analysis(ctx, file_path, project_path):
    """Analisa as dependências de entrada e saída de um arquivo Python."""
    arguments = ctx.params
    with ExecutionLogger('impact-analysis', project_path, arguments) as logger:
        click.echo(Fore.CYAN + f"--- [IMPACT-ANALYSIS] Analisando conexões para '{os.path.relpath(file_path, project_path)}' ---")

        config = _get_project_config(logger, start_path=project_path)
        if not config.get('search_path_valid'):
            # Usa a apresentação customizada mesmo em caso de erro inicial
            _present_impact_results([], [])
            return

        search_path = config.get('search_path')
        ignore_patterns = {item.strip('/\\') for item in config.get('ignore', [])}

        target_module_name = _path_to_module_name(file_path, search_path)
        
        # 1. Analisa dependências de entrada
        inbound_deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=file_path)
            import_visitor = ImportVisitor()
            import_visitor.visit(tree)
            inbound_deps = list(import_visitor.imports)
        except Exception as e:
            logger.add_finding('ERROR', "Não foi possível analisar o arquivo de destino.", details=str(e))
            _present_impact_results([], []) # Apresenta o resultado parcial
            return

        # 2. Analisa dependentes
        outbound_dependents = []
        for root, dirs, files in os.walk(search_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in ignore_patterns]

            for file in files:
                if not file.endswith('.py'): continue
                
                current_file_path = os.path.join(root, file)
                if os.path.samefile(current_file_path, file_path): continue

                try:
                    with open(current_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if not content or target_module_name not in content: continue
                        tree = ast.parse(content, filename=current_file_path)
                    
                    visitor = ImportVisitor()
                    visitor.visit(tree)
                    
                    if target_module_name in visitor.imports:
                        outbound_dependents.append(os.path.relpath(current_file_path, project_path))
                except Exception:
                    continue
        
        # Apresenta os resultados de forma estruturada
        _present_impact_results(inbound_deps, outbound_dependents)