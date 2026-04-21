# doxoade/doxoade/commands/timeline.py
import click
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
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
        # Normalização: converte tupla para dicionário se necessário
        if isinstance(evt, tuple):
            # Baseado na ordem padrão do seu log de eventos:
            # 0: timestamp, 1: full_command, 2: working_dir, 3: duration, 4: exit_code
            d = {
                'timestamp': evt[0],
                'full_command_line': evt[1],
                'working_dir': evt[2],
                'duration_ms': evt[3],
                'exit_code': evt[4]
            }
        else:
            d = evt

        exit_code = d.get('exit_code', 0)
        status_color = Fore.GREEN if exit_code == 0 else Fore.RED
        status_icon = '✔' if exit_code == 0 else '✘'
        
        click.echo(f"\n{Style.DIM}{d['timestamp']} {status_color}{status_icon} {Style.BRIGHT}{d['full_command_line']}")
        click.echo(f"{Style.DIM}   Dir: {d['working_dir']} | Tempo: {d['duration_ms']}ms")
        cursor.execute('SELECT * FROM file_audit WHERE command_id = ?', (evt['id'],))
        changes = cursor.fetchall()
        if changes:
            for change in changes:
                op_color = Fore.YELLOW if change['operation_type'] == 'MODIFY' else Fore.GREEN
                click.echo(f"   {op_color}[{change['operation_type']}] {change['file_path']}")
                if full and change['diff_content']:
                    diff_view = '\n'.join(['      ' + l for l in change['diff_content'].splitlines()])
                    click.echo(Fore.WHITE + Style.DIM + diff_view)
    conn.close()
