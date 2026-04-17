# doxoade/doxoade/commands/telemetry.py
"""
MaxTelemetry v3.9 - Nexus Gold Edition.
Compliance: MPoT-1, PASC-1. Deepcheck Score 100.
"""
import click
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
import json
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection
from . import telemetry_utils as utils
from . import telemetry_io as io

@click.command('telemetry')
@click.option('--limit', '-n', default=10, help='Número de registros.')
@click.option('--command', '-c')
@click.option('--stats', '-s', is_flag=True)
@click.option('--verbose', '-v', is_flag=True, help='Mostra gargalos de código (Hot Lines).')
@click.option('--flow', '-f', is_flag=True, help='Mapa de fluxo entre arquivos + caminho crítico.')
@click.option('--context', '-x', default=3, help='Linhas de contexto ANTES da hot-line (padrão: 3).')
@click.option('--after', '-a', default=2, help='Linhas de contexto DEPOIS da hot-line (padrão: 2).')
def telemetry(limit, command, stats, verbose, flow, context, after):
    """Análise profunda de Recursos (MPoT-12)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM command_history ORDER BY id DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        click.echo(f'{Fore.CYAN}{Style.BRIGHT}=== 📊 DOXOADE NEXUS TELEMETRY ==={Style.RESET_ALL}')
        for row in rows:
            _render_entry(row, verbose, flow, context, after)
    finally:
        conn.close()

def _render_entry(row, verbose: bool, flow: bool, context: int, after: int):
    status = Fore.GREEN + '✔' if row['exit_code'] == 0 else Fore.RED + '✘'
    ts = row['timestamp'][:19].replace('T', ' ')
    cmd = row['command_name'].upper()
    click.echo(f'\n{status} {Fore.WHITE}{ts} | {cmd} ({row['duration_ms']:.0f}ms)')
    if cmd.startswith('VULCAN_EXT_'):
        full_cmd = row['full_command_line'] or ''
        if full_cmd:
            parts = full_cmd.split(' ', 1)
            exe = parts[0].replace('\\', '/').split('/')[-1]
            args = parts[1] if len(parts) > 1 else ''
            click.echo(f'   {Style.DIM}cmd: {Fore.CYAN}{exe}{Style.RESET_ALL}{Style.DIM} {args}{Style.RESET_ALL}')
    io.render_resource_line('PROCESS', row['cpu_percent'], f'{row['cpu_percent']:.1f}%', Fore.YELLOW, 100, '')
    io.render_resource_line('MEMORY', row['peak_memory_mb'], f'{row['peak_memory_mb']:.1f} MB', Fore.MAGENTA, 512, '')
    if row['system_info']:
        try:
            sys_info = json.loads(row['system_info'])
            vulcan_stats = sys_info.get('vulcan_stats')
            if vulcan_stats:
                io.render_vulcan_stats(vulcan_stats, verbose)
        except Exception:
            pass
    if verbose:
        if row['line_profile_data']:
            try:
                hot_data = json.loads(row['line_profile_data'])
                if hot_data:
                    io.render_hot_lines(hot_data)
            except Exception:
                pass
        if row['system_info']:
            try:
                sys_info = json.loads(row['system_info'])
                lib_hot_data = sys_info.get('lib_hot_lines')
                if lib_hot_data:
                    io.render_lib_hot_lines(lib_hot_data)
            except Exception:
                pass
    if flow:
        _render_flow(row, verbose, context_before=context, context_after=after)

def _render_flow(row, verbose: bool, context_before: int=3, context_after: int=2):
    """
    Monta e exibe o fluxo de dados entre arquivos.

    build_flow_data separa automaticamente proj de libs mesmo quando o
    profiler mistura os dois em line_profile_data.

    render_critical_chain exibe context_before linhas antes e context_after
    linhas depois de cada hot-line, mostrando tanto o que causou quanto
    o que o gargalo propaga.
    """
    proj_data: list = []
    lib_data: list = []
    if row['line_profile_data']:
        try:
            proj_data = json.loads(row['line_profile_data']) or []
        except Exception:
            pass
    if row['system_info']:
        try:
            sys_info = json.loads(row['system_info'])
            lib_data = sys_info.get('lib_hot_lines') or []
        except Exception:
            pass
    if not proj_data and (not lib_data):
        click.echo(f'   {Style.DIM}(sem dados de line_profile para o fluxo){Style.RESET_ALL}')
        return
    flow_data = utils.build_flow_data(proj_data, lib_data)
    io_read_mb = row['io_read_mb'] or 0.0
    io_write_mb = row['io_write_mb'] or 0.0
    io.render_flow_map(flow_data, io_read_mb, io_write_mb)
    chain_depth = 4 if verbose else 2
    ctx_before = context_before + 1 if verbose else context_before
    ctx_after = context_after + 1 if verbose else context_after
    chain = utils.find_critical_chain(flow_data, max_steps=chain_depth)
    io.render_critical_chain(chain, context_before=ctx_before, context_after=ctx_after)