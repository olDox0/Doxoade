# doxoade/commands/impact_analysis.py
import os
import ast
import click
#from pathlib import Path
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_project_config

def _resolve_relative_import(module_name, level, current_file_module):
    """Converte um import relativo (ex: '..utils') em um nome de módulo absoluto."""
    if level == 0:
        return module_name

    base_path = current_file_module.split('.')
    # Para um arquivo (não __init__.py), o módulo atual é um "arquivo" no "diretório" do pacote.
    # Para um import relativo, precisamos subir a partir do diretório.
    climb_from = base_path[:-1]
    
    # Sobe 'level' - 1 diretórios. O primeiro '.' já está contido na estrutura.
    ascended_path = climb_from[:-(level - 1)]
    
    # Se há um nome de módulo (ex: from .. import utils -> 'utils'), anexe-o.
    if module_name:
        full_module = ascended_path + module_name.split('.')
    else:
        full_module = ascended_path
        
    return ".".join(full_module)

class ImportVisitor(ast.NodeVisitor):
    """
    Percorre a AST para encontrar todas as declarações de import,
    resolvendo as que são relativas.
    """
    def __init__(self, current_file_module):
        self.imports = set()
        self.current_file_module = current_file_module

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # 'level' > 0 indica um import relativo (ex: from . import x)
        if node.level > 0:
            resolved_import = _resolve_relative_import(node.module, node.level, self.current_file_module)
            self.imports.add(resolved_import)
        elif node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

def _build_project_index(search_path, ignore_patterns, logger):
    """
    Passo 1: Varre o projeto e cria um índice de todos os módulos e seus imports.
    """
    click.echo(Fore.WHITE + "Construindo índice de dependências do projeto...")
    project_index = {}
    
    for root, dirs, files in os.walk(search_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not d.startswith('.')]

        for file in files:
            if not file.endswith('.py'):
                continue
            
            file_path = os.path.join(root, file)
            module_name = _path_to_module_name(file_path, search_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if not content: continue
                    tree = ast.parse(content, filename=file_path)
                
                visitor = ImportVisitor(module_name)
                visitor.visit(tree)
                
                project_index[module_name] = {
                    "path": os.path.relpath(file_path, search_path),
                    "imports": visitor.imports
                }
            except Exception as e:
                logger.add_finding("WARNING", "Arquivo ignorado durante a indexação devido a erro.", 
                                   category="INDEXING-ERROR", file=file_path, details=str(e))
                continue
    return project_index

def _path_to_module_name(file_path, root_path):
    """Converte um caminho de arquivo em um nome de módulo Python."""
    rel_path = os.path.relpath(file_path, root_path)
    module_path = os.path.splitext(rel_path)[0]
    return module_path.replace(os.sep, '.')

def _present_impact_results(target_module, inbound_deps, outbound_dependents):
    """Apresentação customizada e legível."""
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- Análise de Impacto para '{target_module}' ---")

    click.echo(Fore.YELLOW + f"\n[+] DEPENDE DE ({len(inbound_deps)}):")
    if not inbound_deps:
        click.echo(Fore.WHITE + "    Nenhum módulo importado.")
    else:
        internal_deps = sorted([dep for dep in inbound_deps if dep.startswith('doxoade')])
        external_deps = sorted([dep for dep in inbound_deps if not dep.startswith('doxoade')])
        
        if external_deps:
            click.echo(Fore.WHITE + Style.BRIGHT + "    Bibliotecas Externas/Padrão:")
            for dep in external_deps: click.echo(Fore.WHITE + f"      - {dep}")
        if internal_deps:
            click.echo(Fore.WHITE + Style.BRIGHT + "    Módulos Internos do Projeto:")
            for dep in internal_deps: click.echo(Fore.WHITE + f"      - {dep}")

    click.echo(Fore.YELLOW + f"\n[+] É USADO POR ({len(outbound_dependents)}):")
    if not outbound_dependents:
        click.echo(Fore.WHITE + "    Nenhum outro arquivo no projeto parece importar este módulo.")
    else:
        for dep_path in sorted(outbound_dependents): click.echo(Fore.GREEN + f"    - {dep_path}")
    
    click.echo(Fore.CYAN + Style.BRIGHT + "--------------------------------------")


@click.command('impact-analysis')
@click.pass_context
@click.argument('file_path_arg', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
def impact_analysis(ctx, file_path_arg, project_path):
    """Analisa as dependências de entrada e saída de um arquivo Python."""
    arguments = ctx.params
    with ExecutionLogger('impact-analysis', project_path, arguments) as logger:
        config = _get_project_config(logger, start_path=project_path)
        if not config.get('search_path_valid'): return

        search_path = config.get('search_path')
        ignore_patterns = {item.strip('/\\') for item in config.get('ignore', [])}

        # Passo 1: Construir o índice global
        project_index = _build_project_index(search_path, ignore_patterns, logger)
        
        # Passo 2: Fazer as consultas (agora instantâneas)
        target_module_name = _path_to_module_name(file_path_arg, search_path)

        if target_module_name not in project_index:
            click.echo(Fore.RED + f"Erro: O arquivo '{file_path_arg}' não foi encontrado no índice do projeto (pode estar na lista de ignorados).")
            return

        inbound_deps = project_index[target_module_name].get("imports", set())
        
        outbound_dependents = []
        for module_name, data in project_index.items():
            if target_module_name in data.get("imports", set()):
                outbound_dependents.append(data["path"])

        # Passo 3: Apresentar os resultados
        _present_impact_results(target_module_name, inbound_deps, outbound_dependents)