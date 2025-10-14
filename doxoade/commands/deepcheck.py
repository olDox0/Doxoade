# doxoade/commands/deepcheck.py
#import os
import ast
import sys

import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
# Nenhuma ferramenta compartilhada é necessária para este comando específico.

__version__ = "34.0 Alfa"

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', '-f', 'func_name', default=None, help="Analisa profundamente uma função específica.")
def deepcheck(file_path, func_name):
    """Executa uma análise profunda do fluxo de dados e pontos de risco em um arquivo Python."""
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [DEEPCHECK] Analisando fluxo de '{file_path}' ---")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
    except (SyntaxError, IOError) as e:
        click.echo(Fore.RED + f"[ERRO] Falha ao ler ou analisar o arquivo: {e}")
        sys.exit(1)

    function_dossiers = _analyze_function_flow(tree, content, func_name)

    if not function_dossiers:
            if func_name:
                click.echo(Fore.YELLOW + f"A função '{func_name}' não foi encontrada no arquivo.")
            else:
                click.echo(Fore.YELLOW + "Nenhuma função encontrada no escopo global.")
                click.echo(Fore.CYAN + "   > Lembrete: 'deepcheck' analisa o conteúdo de blocos 'def'. A análise de classes ou do corpo do script ainda não é suportada.")
            return

    # --- Apresentação do Relatório ---
    for dossier in function_dossiers:
        header_color = Fore.MAGENTA if dossier.get('complexity_rank', '').lower() == 'altissima' else Fore.RED if dossier.get('complexity_rank', '').lower() == 'alta' else Fore.YELLOW if dossier.get('complexity_rank', '').lower() == 'média' else Fore.GREEN if dossier.get('complexity_rank', '').lower() == 'baixa' else Fore.CYAN if dossier.get('complexity_rank', '').lower() == 'baixissima' else Fore.WHITE
        click.echo(header_color + Style.BRIGHT + f"\n\n--- Função: '{dossier.get('name')}' (linha {dossier.get('lineno')}) ---")
        click.echo(f"  [Complexidade]: {dossier.get('complexity')} ({dossier.get('complexity_rank')})")

        click.echo(Style.DIM + "  [Entradas (Parâmetros)]")
        params = dossier.get('params', [])
        if not params: click.echo("    - Nenhum parâmetro.")
        for p in params: click.echo(f"    - Nome: {p.get('name')} (Tipo: {p.get('type')})")

        click.echo(Style.DIM + "  [Saídas (Pontos de Retorno)]")
        returns = dossier.get('returns', [])
        if not returns: click.echo("    - Nenhum ponto de retorno explícito.")
        for r in returns: click.echo(f"    - Linha {r.get('lineno')}: Retorna {r.get('type')}")

        click.echo(Fore.YELLOW + "  [Pontos de Risco (Micro Análise de Erros)]")
        risks = dossier.get('risks', [])
        if not risks: click.echo("    - Nenhum ponto de risco óbvio detectado.")
        for risk in risks:
            click.echo(Fore.YELLOW + f"    - AVISO (Linha {risk.get('lineno')}): {risk.get('message')}")
            click.echo(Fore.WHITE + f"      > Detalhe: {risk.get('details')}")

def _analyze_function_flow(tree, content, specific_func=None):
    """Orquestra a análise de fluxo de dados de funções."""
    dossiers = []
    try:
        from radon.visitors import ComplexityVisitor
        complexity_map = {f.name: f.complexity for f in ComplexityVisitor.from_code(content).functions}
    except ImportError:
        # Se radon não estiver instalado, simplesmente não teremos a métrica de complexidade.
        complexity_map = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (not specific_func or node.name == specific_func):
            complexity = complexity_map.get(node.name, 0)
            params = _extract_function_parameters(node)
            returns, risks = _find_returns_and_risks(node)
            
            dossiers.append({
                'name': node.name,
                'lineno': node.lineno,
                'params': params,
                'returns': returns,
                'risks': risks,
                'complexity': complexity,
                'complexity_rank': _get_complexity_rank(complexity)
            })
    return dossiers

def _extract_function_parameters(func_node):
    """Extrai os parâmetros de um nó de função AST."""
    params = []
    for arg in func_node.args.args:
        param_type = ast.unparse(arg.annotation) if arg.annotation else "não anotado"
        params.append({'name': arg.arg, 'type': param_type})
    return params

def _find_returns_and_risks(func_node):
    """Encontra pontos de retorno e de risco dentro de uma função."""
    returns = []
    risks = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value:
            return_type = "literal" if isinstance(node.value, ast.Constant) else "variável" if isinstance(node.value, ast.Name) else "expressão"
            returns.append({'lineno': node.lineno, 'type': return_type})
        
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            risks.append({
                'lineno': node.lineno,
                'message': "Acesso a dicionário/lista sem tratamento.",
                'details': f"Acesso direto a '{ast.unparse(node)}' pode causar 'KeyError' ou 'IndexError'."
            })
    return returns, risks

def _get_complexity_rank(complexity):
    """Classifica a complexidade ciclomática."""
    if complexity > 20: return "Altissima"
    if complexity > 15: return "Alta"
    if complexity > 10: return "Média"
    if complexity > 5: return "Baixa"
    return "Baixissima"