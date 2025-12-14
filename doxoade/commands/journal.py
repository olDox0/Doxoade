import click
import sqlite3
import json
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import ExecutionLogger

@click.command('journal')
@click.option('-n', '--limit', default=10, help="Número de entradas.")
@click.option('--full', is_flag=True, help="Detalhes completos.")
def journal(limit, full):
    """Exibe o Diário de Bordo (Chronos)."""
    with ExecutionLogger('journal', '.', {}) as logger:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            
            if not rows:
                click.echo("Diário vazio.")
                return

            click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- Diário de Bordo ({len(rows)}) ---")
            for row in rows:
                status = Fore.GREEN + "✔" if row['exit_code'] == 0 else Fore.RED + "✘"
                ts = row['timestamp'].replace('T', ' ')[:19]
                cmd = row['command_raw']
                
                click.echo(f"{status} {Fore.YELLOW}[{ts}] {Fore.WHITE}{cmd}")
                
                if full:
                    click.echo(Fore.BLUE + f"    ID: {row['session_id']} | Tempo: {row['duration_ms']:.2f}ms")
                    files = json.loads(row['files_touched'])
                    if files:
                        click.echo(Fore.MAGENTA + "    Arquivos:")
                        for f in files: click.echo(f"      {f}")
                    print()
        except Exception as e:
            click.echo(f"Erro: {e}")
        finally:
            conn.close()
