# -*- coding: utf-8 -*-
"""
Módulo de Observabilidade Avançada (MaxTelemetry v2.8).
Identifica gargalos (Hot Lines) com impacto percentual e contexto de código.
Versão final otimizada para o Ciclo de Ouro v69.
"""

import click, sqlite3
import json
import linecache
import os
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from ..database import get_db_connection

__version__ = "2.8 Alfa (Gold-Profiling-Final)"

def _render_resource_bar(label: str, value: float, max_val: float, color: str):
    """Renderiza uma barra de recurso visual amigável. MPoT-5: Contrato Ativo."""
    if not label:
        raise ValueError("O rótulo da barra é obrigatório.")
        
    console = Console()
    safe_val, safe_max = float(value or 0), float(max_val or 1)
    percent = min(100, (safe_val / safe_max) * 100)
    
    bar_width = 20
    filled = int((percent / 100) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    console.print(f"   {label:<12} [[{color}]{bar}[/{color}]] {safe_val:.1f}")

def _get_hot_line_data(line_json: str) -> List[Dict[str, Any]]:
    """Extrai e processa dados brutos do profiler de linha para visualização."""
    try:
        hot_lines: List[Dict[str, Any]] = json.loads(line_json)
        if not hot_lines:
            return []

        total_hits = sum(item['hits'] for item in hot_lines)
        processed = []
        for item in hot_lines[:5]:
            impacto = (item['hits'] / total_hits * 100) if total_hits > 0 else 0
            # Usa path absoluto para garantir leitura consistente
            file_path = os.path.abspath(item['file'])
            content = linecache.getline(file_path, item['line']).strip()
            
            processed.append({
                'impact': f"{impacto:.1f}%", 
                'loc': f"{item['file']}:{item['line']}", 
                'code': content or "[Código Interno/Dinâmico]"
            })
        return processed
    except (json.JSONDecodeError, TypeError, KeyError):
        return []

def _render_hot_lines_table(data: List[Dict[str, Any]]):
    """Renderiza a tabela de gargalos (Hot Lines). MPoT-5: Contrato Ativo."""
    if data is None:
        raise ValueError("Dados de telemetria ausentes para renderização.")
    if not data:
        return
        
    console = Console()
    table = Table(title="🔥 TOP GARGALOS (Hot Lines)", title_style="bold red", box=box.ROUNDED, expand=True)
    table.add_column("Impacto", justify="right", style="bold red", width=10)
    table.add_column("Localização", style="cyan", overflow="ellipsis", ratio=1)
    table.add_column("Código", style="yellow", overflow="fold", ratio=2)
    
    for entry in data:
        table.add_row(entry['impact'], entry['loc'], entry['code'])
    console.print(table)

def _analyze_processing_detailed(row_data: Dict[str, Any]):
    """Orquestra a análise detalhada de processamento e linhas."""
    if not row_data:
        raise ValueError("Dados de linha obrigatórios para análise detalhada.")
        
    cpu = row_data.get('cpu_percent', 0) or 0
    _render_resource_bar("CPU Usage", cpu, 100, "red" if cpu > 80 else "yellow")
    
    if row_data.get('line_profile_data'):
        _render_hot_lines_table(_get_hot_line_data(row_data['line_profile_data']))

def _print_stats_lean(command_filter: Optional[str]):
    """Gera estatísticas agregadas via SQL Engine para alta performance."""
    conn = get_db_connection()
    console = Console()
    
    if conn is None:
        raise RuntimeError("Banco de dados inacessível.")

    sql = """
        SELECT command_name, COUNT(*) as qtd, AVG(duration_ms) as avg_dur, 
               AVG(cpu_percent) as avg_cpu, AVG(peak_memory_mb) as avg_ram 
        FROM command_history
    """
    
    try:
        if command_filter:
            rows = conn.execute(sql + " WHERE LOWER(command_name) = ? GROUP BY command_name", 
                                (command_filter.lower(),)).fetchall()
        else:
            rows = conn.execute(sql + " GROUP BY command_name ORDER BY avg_dur DESC").fetchall()
            
        table = Table(title="📈 Médias de Performance (Lean SQL)", box=box.SIMPLE)
        table.add_column("Comando", style="cyan")
        table.add_column("Qtd", justify="center")
        table.add_column("Tempo", justify="right")
        table.add_column("CPU %", justify="right")
        table.add_column("RAM", justify="right")
        
        for r in rows:
            table.add_row(str(r[0]), str(r[1]), f"{r[2]:.0f}ms", f"{r[3]:.1f}%", f"{r[4]:.1f}MB")
        console.print(table)
    finally:
        conn.close()

def _fetch_history_rows(limit: int, command: Optional[str]) -> List[sqlite3.Row]:
    """Recupera os registros do histórico com segurança contra SQL Injection."""
    conn = get_db_connection()
    try:
        if command:
            return conn.execute(
                "SELECT * FROM command_history WHERE LOWER(command_name) = ? ORDER BY id DESC LIMIT ?", 
                (command.lower(), limit)
            ).fetchall()
        return conn.execute(
            "SELECT * FROM command_history ORDER BY id DESC LIMIT ?", 
            (limit,)
        ).fetchall()
    finally:
        conn.close()

@click.command('telemetry')
@click.option('--limit', '-n', default=5, help="Últimos N registros.")
@click.option('--command', '-c', help="Filtra por comando.")
@click.option('--stats', '-s', is_flag=True, help="Estatísticas de médias (Lean).")
@click.option('--verbose', '-v', is_flag=True, help="Detalhes completos e Hot Lines.")
def telemetry(limit, command, stats, verbose):
    """Diagnóstico de performance de hardware e gargalos de código."""
    # MPoT-5: Contrato Blindado na entrada do comando
    if limit < 1:
        raise click.BadParameter("O limite deve ser um número inteiro positivo.")

    if stats:
        _print_stats_lean(command)
        return

    rows = _fetch_history_rows(limit, command)
    if not rows:
        click.echo("Nenhum dado encontrado no histórico Chronos.")
        return

    console = Console()
    console.print(Panel.fit("[bold cyan]📊 DOXOADE MAX TELEMETRY v2.8[/bold cyan]"))

    for r in rows:
        data = dict(r)
        status = "[green]✔[/green]" if data['exit_code'] == 0 else "[red]✘[/red]"
        console.print(f"\n{status} [bold white]{data['timestamp'][:19]}[/bold white] | [magenta]{data['command_name'].upper()}[/magenta]")
        
        if verbose or (data['cpu_percent'] and data['cpu_percent'] > 50):
            _analyze_processing_detailed(data)
        else:
            _render_resource_bar("CPU Usage", data['cpu_percent'], 100, "yellow")

        if verbose:
            ram = data['peak_memory_mb'] or 0
            _render_resource_bar("Memory", ram, 512, "magenta")
            console.print(f"   [dim]I/O Read: {data['io_read_mb']:.2f}MB | Write: {data['io_write_mb']:.2f}MB[/dim]")