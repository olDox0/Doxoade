# doxoade/commands/history.py
import click
import sqlite3
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _format_timestamp

@click.command('history')
@click.pass_context
@click.option('--hash', 'finding_hash', help="Procura uma solução por um hash de erro específico.")
@click.option('--message', help="Procura soluções por texto na mensagem do erro.")
def history(ctx, finding_hash, message):
    """Consulta o banco de dados de soluções aprendidas."""
    with ExecutionLogger('history', '.', ctx.params) as logger:
        conn = get_db_connection()
        # Usa Row factory para acessar colunas por nome
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Constrói a query dinamicamente
        query = "SELECT * FROM solutions WHERE 1=1"
        params = []
        
        if finding_hash:
            query += " AND finding_hash LIKE ?"
            params.append(f"%{finding_hash}%")
        if message:
            query += " AND message LIKE ?"
            params.append(f"%{message}%")
        
        query += " ORDER BY timestamp DESC LIMIT 20" # Limita para não poluir

        try:
            cursor.execute(query, params)
            solutions = cursor.fetchall()

            if not solutions:
                click.echo(Fore.YELLOW + "Nenhuma solução encontrada para os critérios informados.")
                return

            click.echo(Fore.CYAN + f"--- {len(solutions)} Solução(ões) Encontrada(s) (Recentes) ---")
            
            for sol in solutions:
                click.echo(Style.BRIGHT + "\n[SOLUÇÃO PARA O ERRO]")
                click.echo(f"  - {Fore.WHITE}{sol['message']}{Style.RESET_ALL}")
                click.echo(f"  - {Fore.YELLOW}Hash do Erro:{Style.RESET_ALL} {sol['finding_hash']}")
                click.echo(f"  - {Fore.YELLOW}Arquivo:{Style.RESET_ALL} {sol['file_path']}")
                
                # Formata a data
                local_date = _format_timestamp(sol['timestamp'])
                click.echo(f"  - {Fore.YELLOW}Data:{Style.RESET_ALL} {local_date}")
                
                click.echo(f"\n{Fore.MAGENTA}--- Conteúdo Estável (Pós-Correção) ---{Style.RESET_ALL}")
                
                # Mostra apenas as linhas relevantes se possível, ou um resumo
                content = sol['stable_content']
                error_line = sol['error_line']
                
                if error_line and isinstance(error_line, int):
                    # Mostra contexto ao redor da linha do erro
                    lines = content.splitlines()
                    start = max(0, error_line - 3)
                    end = min(len(lines), error_line + 3)
                    
                    for i in range(start, end):
                        prefix = " >> " if (i + 1) == error_line else "    "
                        color = Fore.GREEN if (i + 1) == error_line else Fore.WHITE
                        click.echo(f"{color}{prefix}{i+1:4}: {lines[i]}")
                else:
                    # Se não tiver linha, mostra tudo (cuidado com arquivos grandes)
                    click.echo(content[:500] + "..." if len(content) > 500 else content)
                    
                click.echo(Fore.MAGENTA + "-"*40 + Style.RESET_ALL)

        except Exception as e:
            logger.add_finding("ERROR", "Falha ao consultar o histórico.", details=str(e))
            click.echo(Fore.RED + f"Erro ao consultar banco de dados: {e}")
        finally:
            conn.close()