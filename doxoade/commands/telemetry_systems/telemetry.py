# -*- coding: utf-8 -*-
# doxoade/commands/telemetry_systems/telemetry.py
"""
MaxTelemetry v4.1 - Nexus Gold Edition.
Suporte a visualização de Matrix, exportação JSON e gravação em arquivo.
"""
from __future__ import annotations

import click
import json
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.core_database import get_db_connection
import doxoade.tools.aegis.nexus_db as sqlite3 

from . import telemetry_utils as utils
from . import telemetry_io as io
from .shadow_matrix import ShadowMatrix


@click.command('telemetry')
@click.option('--limit', '-n', default=10, help='Número de registros do histórico.')
@click.option('--command', '-c', help='Filtra por nome de comando específico.')
@click.option('--stats', '-s', is_flag=True, help='Exibe tabela agregada de performance.')
@click.option('--verbose', '-v', is_flag=True, help='Mostra gargalos de código (Hot Lines).')
@click.option('--flow', '-f', is_flag=True, help='Mapa de fluxo entre arquivos + caminho crítico.')
@click.option('--matrix', '-m', is_flag=True, help='🦅 Exibe o HUD da Shadow Timeline Matrix do último comando profilado.')
@click.option('--dump-id', type=str, default=None, help='Timestamp ou caminho de um dump específico para carregar na Matrix.')
@click.option('--json', 'as_json', is_flag=True, help='Exporta os dados em formato JSON no stdout.')
@click.option('--output', '-o', type=click.Path(dir_okay=False, writable=True), default=None, help='Salva o JSON completo em um arquivo especificado.')
@click.option('--context', '-x', default=3, help='Linhas de contexto ANTES da hot-line (padrão: 3).')
@click.option('--after', '-a', default=2, help='Linhas de contexto DEPOIS da hot-line (padrão: 2).')
@click.option('--boot', is_flag=True, help='⚡ Exibe o laudo analítico e ranking de tempo do Boot do Doxoade.')
def telemetry(limit, command, stats, verbose, flow, matrix, dump_id, as_json, output, context, after, boot):
    """Análise profunda de Recursos e Linha do Tempo (MPoT-12)."""
    # Rota de Inspeção de Boot
    if boot:
        _render_boot_analysis()
        return
    # 1. Rota da Shadow Matrix (HUD, JSON stdout ou Arquivo)
    if matrix or dump_id or output:
        data = None
        if dump_id:
            dump_file = Path(dump_id)
            if not dump_file.exists():
                dump_file = Path.home() / ".doxoade" / "shadow_profiling" / f"{dump_id}.json"
            if dump_file.exists():
                data = json.loads(dump_file.read_text(encoding="utf-8"))
            else:
                click.secho(f"Dump não encontrado: {dump_id}", fg="red")
                return
        else:
            data = ShadowMatrix.load_last_dump()

        if not data:
            click.secho("Nenhum snapshot de Shadow Matrix encontrado em ~/.doxoade/shadow_profiling/.", fg="yellow")
            return

        json_payload = json.dumps(data, indent=2)

        # Gravação direta em arquivo
        if output:
            out_path = Path(output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json_payload, encoding="utf-8")
            click.secho(f"✔ Dossiê JSON gravado com sucesso em: {out_path}", fg="green")
            return

        # Saída em stdout ou HUD visual
        if as_json:
            click.echo(json_payload)
        else:
            ShadowMatrix.render_data_hud(data)
        return

    # 2. Rota Clássica de Histórico do Banco SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM command_history"
        params = []
        if command:
            query += " WHERE command_name = ?"
            params.append(command.lower())
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

        click.echo(f"{Fore.CYAN}{Style.BRIGHT}=== 📊 DOXOADE NEXUS TELEMETRY ==={Style.RESET_ALL}")
        for row in rows:
            row_dict = dict(zip(columns, row))
            _render_entry(row_dict, verbose, flow, context, after)
    finally:
        conn.close()

def _render_boot_analysis():
    """Renderiza a anatomia das fases de arranque do Doxoade."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT timestamp, data FROM operational_logs 
            WHERE subsystem = 'BOOT' AND action = 'IGNITE_SUCCESS' 
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            click.secho("Nenhum registro de telemetria de boot localizado na base.", fg="yellow")
            return

        ts, data_raw = row[0], row[1]
        boot_data = json.loads(data_raw)
        total_ms = boot_data.get("total_ms", 0.0)
        phases = boot_data.get("phases", {})

        from rich.console import Console
        from rich.table import Table
        c = Console()

        table = Table(
            title=f"⚡ DOXOADE BOOT TELEMETRY ({ts[:19]} | Total: [bold green]{total_ms:.1f}ms[/bold green])",
            header_style="bold cyan",
            border_style="dim cyan"
        )
        table.add_column("Fase de Arranque", style="white")
        table.add_column("Duração (ms)", justify="right", style="bold yellow")
        table.add_column("% do Boot", justify="right", style="bold red")

        sorted_phases = sorted(phases.items(), key=lambda x: x[1], reverse=True)
        for name, dur in sorted_phases:
            pct = (dur / total_ms * 100.0) if total_ms > 0 else 0.0
            table.add_row(name, f"{dur:.2f} ms", f"{pct:.1f}%")

        c.print("\n")
        c.print(table)
        c.print("\n")
    finally:
        conn.close()

def _render_entry(row, verbose: bool, flow: bool, context: int, after: int):
    status = Fore.GREEN + '✔' if row['exit_code'] == 0 else Fore.RED + '✘'
    ts = row['timestamp'][:19].replace('T', ' ')
    cmd = row['command_name'].upper()
    click.echo(f"\n{status} {Fore.WHITE}{ts} | {cmd} ({row['duration_ms']:.0f}ms)")
    if cmd.startswith('VULCAN_EXT_'):
        full_cmd = row['full_command_line'] or ''
        if full_cmd:
            parts = full_cmd.split(' ', 1)
            exe = parts[0].replace('\\', '/').split('/')[-1]
            args = parts[1] if len(parts) > 1 else ''
            click.echo(f'   {Style.DIM}cmd: {Fore.CYAN}{exe}{Style.RESET_ALL}{Style.DIM} {args}{Style.RESET_ALL}')
    io.render_resource_line('PROCESS', row['cpu_percent'], f"{row['cpu_percent']:.1f}%", Fore.YELLOW, 100, '')
    io.render_resource_line('MEMORY', row['peak_memory_mb'], f"{row['peak_memory_mb']:.1f} MB", Fore.MAGENTA, 512, '')
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


def _render_flow(row, verbose: bool, context_before: int = 3, context_after: int = 2):
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
