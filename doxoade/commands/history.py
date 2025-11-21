# doxoade/commands/history.py
import click
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _present_diff_output # <-- IMPORTE A FUNÇÃO AQUI

def _format_diff(diff_text):
    """Colore a saída do diff para melhor legibilidade."""
    lines = []
    for line in diff_text.split('\n'):
        if line.startswith('+'):
            lines.append(Fore.GREEN + line + Style.RESET_ALL)
        elif line.startswith('-'):
            lines.append(Fore.RED + line + Style.RESET_ALL)
        elif line.startswith('@@'):
            lines.append(Fore.CYAN + line + Style.RESET_ALL)
        else:
            lines.append(line)
    return '\n'.join(lines)

@click.command('history')
@click.pass_context
@click.option('--hash', 'finding_hash', help="Procura uma solução por um hash de erro específico.")
@click.option('--message', help="Procura soluções por texto na mensagem do erro.")
def history(ctx, finding_hash, message):
    """Consulta o banco de dados de soluções aprendidas."""
    with ExecutionLogger('history', '.', ctx.params) as logger:
        conn = get_db_connection()
        conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cursor = conn.cursor()

        query = "SELECT * FROM solutions WHERE 1=1"
        params = []
        if finding_hash:
            query += " AND finding_hash LIKE ?"
            params.append(f"%{finding_hash}%")
        if message:
            query += " AND message LIKE ?"
            params.append(f"%{message}%")
        
        query += " ORDER BY timestamp DESC"

        try:
            cursor.execute(query, params)
            solutions = cursor.fetchall()

            if not solutions:
                click.echo(Fore.YELLOW + "Nenhuma solução encontrada para os critérios informados.")
                return

            click.echo(Fore.CYAN + f"--- {len(solutions)} Solução(ões) Encontrada(s) ---")
            for sol in solutions:
                click.echo(Style.BRIGHT + "\n[SOLUÇÃO PARA O ERRO]")
                click.echo(f"  - {Fore.WHITE}{sol['message']}{Style.RESET_ALL}")
                click.echo(f"  - {Fore.YELLOW}Hash do Erro:{Style.RESET_ALL} {sol['finding_hash']}")
                click.echo(f"  - {Fore.YELLOW}Arquivo:{Style.RESET_ALL} {sol['file_path']}")
                click.echo(f"  - {Fore.YELLOW}Commit da Solução:{Style.RESET_ALL} {sol['commit_hash']}")
                click.echo(f"  - {Fore.YELLOW}Data:{Style.RESET_ALL} {sol['timestamp']}")
                click.echo(f"\n{Fore.MAGENTA}--- Correção Aplicada (Diff) ---{Style.RESET_ALL}")
                click.echo(_format_diff(sol['resolution_diff']))
                _present_diff_output(sol['resolution_diff']) 
                
                click.echo(Fore.MAGENTA + "--------------------------------" + Style.RESET_ALL)

        except Exception as e:
            logger.add_finding("ERROR", "Falha ao consultar o histórico de soluções.", details=str(e))
            click.echo(Fore.RED + f"Erro ao consultar banco de dados: {e}")
        finally:
            conn.close()