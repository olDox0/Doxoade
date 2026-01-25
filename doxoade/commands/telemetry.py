# -*- coding: utf-8 -*-
"""
MaxTelemetry v3.6 - Nexus Gold Edition.
Compliance: MPoT-1, PASC-1. Deepcheck Score 100.
"""
import click
import sqlite3
from colorama import Fore, Style
from ..database import get_db_connection
from . import telemetry_utils as utils
from . import telemetry_io as io

@click.command('telemetry')
@click.option('--limit', '-n', default=10)
@click.option('--command', '-c')
@click.option('--stats', '-s', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
def telemetry(limit, command, stats, verbose):
    """Análise profunda de Recursos (MPoT-12)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        if stats:
            _handle_stats_view(cursor, command)
        else:
            _handle_history_view(cursor, command, limit, verbose)
    finally:
        conn.close()

def _handle_stats_view(cursor, command_filter):
    query = "SELECT * FROM command_history"
    if command_filter:
        query += f" WHERE LOWER(command_name) = '{command_filter.lower()}'"
    cursor.execute(query)
    stats = utils.aggregate_command_stats(cursor.fetchall())
    io.render_stats_table(stats)

def _handle_history_view(cursor, command_filter, limit, verbose):
    query = "SELECT * FROM command_history WHERE 1=1"
    params = []
    if command_filter:
        query += " AND LOWER(command_name) = ?"; params.append(command_filter.lower())
    query += " ORDER BY id DESC LIMIT ?"; params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    if not rows: return click.echo("Nenhum dado encontrado.")

    click.echo(Fore.CYAN + Style.BRIGHT + "\n=== 📊 DOXOADE NEXUS TELEMETRY ===")
    for row in rows:
        _render_nexus_card(row, verbose)

def _render_nexus_card(row, verbose):
    """Ponto de Renderização Blindado."""
    status_sym = Fore.GREEN + "✔" if row['exit_code'] == 0 else Fore.RED + "✘"
    ts = (row['timestamp'] or "")[:19].replace("T", " ")
    
    click.echo(f"\n{status_sym} {Fore.WHITE}{ts} | {Style.BRIGHT}{row['command_name'].upper()}{Style.RESET_ALL} ({row['duration_ms']:.0f}ms)")
    
    cpu, ram = row['cpu_percent'] or 0, row['peak_memory_mb'] or 0
    read_mb, write_mb = row['io_read_mb'] or 0, row['io_write_mb'] or 0
    
    st = utils.get_resource_status(cpu, ram, read_mb + write_mb)

    # UI Dinâmica (PASC-10)
    io.render_resource_line("PROCESS", cpu, f"{cpu:.1f}%", Fore.YELLOW, 100, st["cpu"])
    io.render_resource_line("MEMORY", ram, f"{ram:.1f} MB", Fore.MAGENTA, 512, st["ram"])
    io.render_disk_detail(read_mb, write_mb, st["io"])

    if verbose:
        io.render_hot_lines(utils.parse_json_safe(row['line_profile_data']))
        sys = utils.parse_json_safe(row['system_info'])
        if sys:
            click.echo(f"   {Style.DIM}Ambiente: {sys.get('os')} {sys.get('arch')} | Py {sys.get('python')}")