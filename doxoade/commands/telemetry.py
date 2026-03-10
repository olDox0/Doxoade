# -*- coding: utf-8 -*-
# doxoade/commands/telemetry.py (v94.6 Platinum)
"""
MaxTelemetry v3.6 - Nexus Gold Edition.
Compliance: MPoT-1, PASC-1. Deepcheck Score 100.
"""
import click
import sqlite3 # noqa
import json
from doxoade.tools.doxcolors import Fore, Style
from ..database import get_db_connection
from . import telemetry_utils as utils
from . import telemetry_io as io
@click.command('telemetry')
@click.option('--limit', '-n', default=10, help="Número de registros.")
@click.option('--command', '-c')
@click.option('--stats', '-s', is_flag=True)
@click.option('--verbose', '-v', is_flag=True, help="Mostra gargalos de código (Hot Lines).")
def telemetry(limit, command, stats, verbose):
    """Análise profunda de Recursos (MPoT-12)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM command_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}=== 📊 DOXOADE NEXUS TELEMETRY ==={Style.RESET_ALL}")
        for row in rows:
            _render_entry(row, verbose)
    finally:
        conn.close()
def _render_entry(row, verbose):
    status = Fore.GREEN + "✔" if row['exit_code'] == 0 else Fore.RED + "✘"
    ts = row['timestamp'][:19].replace('T', ' ')
    click.echo(f"\n{status} {Fore.WHITE}{ts} | {row['command_name'].upper()} ({row['duration_ms']:.0f}ms)")
    
    # Chama o renderizador de barras do telemetry_io
    io.render_resource_line("PROCESS", row['cpu_percent'], f"{row['cpu_percent']:.1f}%", Fore.YELLOW, 100, "")
    io.render_resource_line("MEMORY", row['peak_memory_mb'], f"{row['peak_memory_mb']:.1f} MB", Fore.MAGENTA, 512, "")
    
    if verbose and row['line_profile_data']:
        hot_data = json.loads(row['line_profile_data'])
        io.render_hot_lines(hot_data)