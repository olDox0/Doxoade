# doxoade/doxoade/commands/timeline.py
import click
import sqlite3
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection

@click.command('timeline')
@click.option('-n', '--limit', default=10, help='Número de eventos.')
@click.option('--full', is_flag=True, help='Mostra o diff completo das alterações.')
def timeline(limit, full):
    """Exibe o histórico cronológico de ações e alterações."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('\n        SELECT * FROM command_history \n        ORDER BY id DESC LIMIT ?\n    ', (limit,))
    events = cursor.fetchall()
    click.echo(Fore.CYAN + Style.BRIGHT + f'--- Timeline do Doxoade (Últimos {limit}) ---')
    for evt in reversed(events):
        status_color = Fore.GREEN if evt['exit_code'] == 0 else Fore.RED
        status_icon = '✔' if evt['exit_code'] == 0 else '✘'
        click.echo(f'\n{Style.DIM}{evt['timestamp']} {status_color}{status_icon} {Style.BRIGHT}{evt['full_command_line']}')
        click.echo(f'{Style.DIM}   Dir: {evt['working_dir']} | Tempo: {evt['duration_ms']}ms')
        cursor.execute('SELECT * FROM file_audit WHERE command_id = ?', (evt['id'],))
        changes = cursor.fetchall()
        if changes:
            for change in changes:
                op_color = Fore.YELLOW if change['operation_type'] == 'MODIFY' else Fore.GREEN
                click.echo(f'   {op_color}[{change['operation_type']}] {change['file_path']}')
                if full and change['diff_content']:
                    diff_view = '\n'.join(['      ' + l for l in change['diff_content'].splitlines()])
                    click.echo(Fore.WHITE + Style.DIM + diff_view)
    conn.close()