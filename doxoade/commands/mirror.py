# doxoade/commands/mirror.py
import os
import sys
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

def _read_file_lines(file_path, logger):
    """Lê um arquivo e retorna seu conteúdo como um conjunto de linhas."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            # Usamos strip() para ignorar diferenças de quebra de linha e espaços em branco
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        msg = f"Arquivo não encontrado: {file_path}"
        logger.add_finding("ERROR", msg, category="FILE-NOT-FOUND")
        click.echo(Fore.RED + f"[ERRO] {msg}")
        return None
    except Exception as e:
        logger.add_finding("ERROR", f"Falha ao ler o arquivo: {file_path}", details=str(e))
        click.echo(Fore.RED + f"[ERRO] Falha ao ler o arquivo '{file_path}': {e}")
        return None

@click.command('mirror')
@click.pass_context
@click.argument('file_a_path', type=click.Path())
@click.argument('file_b_path', type=click.Path())
def mirror(ctx, file_a_path, file_b_path):
    """
    Compara o conteúdo de dois arquivos e mostra as diferenças.
    """
    arguments = ctx.params
    with ExecutionLogger('mirror', '.', arguments) as logger:
        
        # Garante que os caminhos sejam absolutos para clareza na saída
        file_a_path = os.path.abspath(file_a_path)
        file_b_path = os.path.abspath(file_b_path)
        
        click.echo(Fore.CYAN + "--- [MIRROR] Comparando arquivos ---")
        click.echo(Fore.WHITE + f"  A: {file_a_path}")
        click.echo(Fore.WHITE + f"  B: {file_b_path}")
        
        lines_a = _read_file_lines(file_a_path, logger)
        if lines_a is None:
            sys.exit(1)
            
        lines_b = _read_file_lines(file_b_path, logger)
        if lines_b is None:
            sys.exit(1)

        # Compara os conjuntos de linhas
        only_in_a = sorted(list(lines_a - lines_b))
        only_in_b = sorted(list(lines_b - lines_a))
        
        click.echo(Style.BRIGHT + "\n--- Resultado da Comparação ---")

        if not only_in_a and not only_in_b:
            click.echo(Fore.GREEN + "[OK] Os arquivos são funcionalmente idênticos (ignorando a ordem e linhas em branco).")
            logger.add_finding("INFO", "Arquivos idênticos.", category="COMPARISON")
            return

        # Mostra as linhas que só existem no Arquivo A
        if only_in_a:
            click.echo(Fore.YELLOW + f"\n[+] Apenas em A ({os.path.basename(file_a_path)}):")
            for line in only_in_a:
                click.echo(Fore.GREEN + f"    + {line}")
            logger.add_finding("INFO", f"Encontradas {len(only_in_a)} linhas exclusivas em A.", category="DIFF")

        # Mostra as linhas que só existem no Arquivo B
        if only_in_b:
            click.echo(Fore.YELLOW + f"\n[+] Apenas em B ({os.path.basename(file_b_path)}):")
            for line in only_in_b:
                click.echo(Fore.RED + f"    - {line}")
            logger.add_finding("INFO", f"Encontradas {len(only_in_b)} linhas exclusivas em B.", category="DIFF")