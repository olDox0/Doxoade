# doxoade/commands/deepcheck.py
import sys
import click
from colorama import Fore, Style

# Importa a nova função centralizada de análise de estrutura
from ..shared_tools import analyze_file_structure

@click.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', '-f', 'func_name', default=None, help="Analisa profundamente uma função específica.")
def deepcheck(file_path, func_name):
    """Executa uma análise profunda do fluxo de dados e pontos de risco em um arquivo Python."""
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [DEEPCHECK] Analisando fluxo de '{file_path}' ---")
    
    # Chama a função centralizada para obter os dados
    analysis_result = analyze_file_structure(file_path)

    if analysis_result.get('error'):
        click.echo(Fore.RED + f"[ERRO] {analysis_result['error']}")
        sys.exit(1)

    function_dossiers = analysis_result.get('functions', [])

    # Filtra por uma função específica, se solicitado
    if func_name:
        function_dossiers = [d for d in function_dossiers if d.get('name') == func_name]

    if not function_dossiers:
        if func_name:
            click.echo(Fore.YELLOW + f"A função '{func_name}' não foi encontrada no arquivo.")
        else:
            click.echo(Fore.YELLOW + "Nenhuma função encontrada no escopo global.")
        return

    # A lógica de apresentação permanece a mesma
    for dossier in function_dossiers:
        complexity_rank = dossier.get('complexity_rank', '').lower()
        color_map = {
            'altissima': Fore.MAGENTA, 'alta': Fore.RED, 'média': Fore.YELLOW,
            'baixa': Fore.GREEN, 'baixissima': Fore.CYAN
        }
        header_color = color_map.get(complexity_rank, Fore.WHITE)
        
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