# doxoade/commands/history.py
import click
import sys
from colorama import Fore, Style

from ..database import get_db_connection
from ..shared_tools import ExecutionLogger

def _format_diff(diff_text):
    """Formata a saída do 'git diff' com cores para melhor legibilidade."""
    if not diff_text:
        return Fore.YELLOW + "    (Nenhum diff de texto disponível para esta solução)"

    formatted_lines = []
    for line in diff_text.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            formatted_lines.append(Fore.GREEN + line)
        elif line.startswith('-') and not line.startswith('---'):
            formatted_lines.append(Fore.RED + line)
        elif line.startswith('@@'):
            formatted_lines.append(Fore.CYAN + line)
        else:
            formatted_lines.append(Fore.WHITE + line)
    return Style.RESET_ALL + "\n".join(formatted_lines)

@click.command('history')
@click.pass_context
@click.argument('search_terms', nargs=-1)
def history(ctx, search_terms):
    """
    Pesquisa no banco de dados por soluções aprendidas para problemas passados.
    """
    arguments = ctx.params
    with ExecutionLogger('history', '.', arguments) as logger:
        if not search_terms:
            click.echo(Fore.YELLOW + "Uso: doxoade history <termo1> [termo2] ...")
            click.echo("Exemplo: doxoade history \"imported but unused\"")
            return

        click.echo(Fore.CYAN + f"--- [HISTORY] Procurando soluções para: '{' '.join(search_terms)}' ---")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Busca diretamente na tabela 'solutions' pela mensagem
            base_query = "SELECT * FROM solutions WHERE "
            conditions = " AND ".join(["message LIKE ?"] * len(search_terms))
            params = [f"%{term}%" for term in search_terms]
            query = base_query + conditions + " ORDER BY timestamp DESC"
            
            cursor.execute(query, params)
            solutions = cursor.fetchall()

            if not solutions:
                click.echo(Fore.YELLOW + "\nNenhuma solução encontrada no histórico para os termos pesquisados.")
                logger.add_finding("INFO", "Nenhuma solução encontrada.", category="HISTORY-SEARCH")
                return

            click.echo(Fore.GREEN + f"\nEncontrada(s) {len(solutions)} solução(ões) no histórico:\n")
            logger.add_finding("INFO", f"{len(solutions)} soluções encontradas.", category="HISTORY-SEARCH")

            for i, sol in enumerate(solutions, 1):
                click.echo(Fore.CYAN + Style.BRIGHT + f"--- Solução #{i} ---")
                click.echo(f"{Fore.WHITE}Problema:   {Style.BRIGHT}{sol['message']}{Style.RESET_ALL}")
                click.echo(f"{Fore.WHITE}Arquivo:    {sol['file_path']}")
                click.echo(f"{Fore.WHITE}Projeto:    {sol['project_path']}")
                click.echo(f"{Fore.WHITE}Resolvido em: {sol['timestamp']}")
                click.echo(Fore.YELLOW + "Correção Aplicada (diff):")
                click.echo(_format_diff(sol['resolution_diff']))
                click.echo(Style.DIM + "-" * 40)

        except Exception as e:
            logger.add_finding("ERROR", "Falha ao consultar o histórico de soluções.", details=str(e))
            click.echo(Fore.RED + f"Erro ao consultar o banco de dados: {e}")
            sys.exit(1)
        finally:
            conn.close()