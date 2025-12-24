# doxoade/commands/telemetry.py
import click
import sqlite3
import json
import statistics
import os
from colorama import Fore, Style
from ..database import get_db_connection

def _draw_bar(value, max_val, width=20, color=Fore.GREEN):
    """Desenha uma barra de progresso visual."""
    if max_val == 0: percent = 0
    else: percent = min(1.0, value / max_val)
    
    fill = int(width * percent)
    bar = "█" * fill + "░" * (width - fill)
    return f"{color}{bar}{Style.RESET_ALL}"

def _analyze_processing(row):
    """Análise detalhada de CPU, Funções e Linhas (Gargalos)."""
    cpu = row['cpu_percent'] or 0
    dur = row['duration_ms'] or 0
    profile_json = row['profile_data']
    line_json = row['line_profile_data'] # [NOVO]
    work_dir = row['working_dir'] or ""

    load_type = "Ocioso"
    color = Fore.GREEN
    if cpu > 80: load_type, color = "Crítico (CPU Bound)", Fore.RED
    elif cpu > 50: load_type, color = "Alto", Fore.YELLOW
    elif cpu > 20: load_type, color = "Moderado", Fore.CYAN

    click.echo(Fore.CYAN + "  ⚙️  [PROCESSAMENTO]")
    click.echo(f"     CPU Usage: {_draw_bar(cpu, 100, color=color)} {cpu}%")
    click.echo(f"     Classificação: {color}{load_type}{Style.RESET_ALL}")
    
    cpu_time = (dur * (cpu/100))
    click.echo(f"     Tempo de CPU Efetivo: {cpu_time:.0f}ms")

    if line_json:
        try:
            hot_lines = json.loads(line_json)
            if hot_lines:
                click.echo(Fore.RED + "     🔥 Hot Lines (Onde o código parou mais vezes):")
                import linecache
                for item in hot_lines:
                    fname = item['file']
                    lineno = item['line']
                    hits = item['hits']
                    
                    # Tenta ler o conteúdo da linha
                    full_path = os.path.abspath(fname)
                    content = linecache.getline(full_path, lineno).strip()
                    if not content: content = "(código não acessível)"
                    
                    click.echo(f"       {Fore.YELLOW}{fname}:{lineno}{Style.RESET_ALL} (Amostras: {hits})")
                    click.echo(f"         > {Style.DIM}{content}{Style.RESET_ALL}")
                    
            if 'system_info' in row.keys() and row['system_info']:
                try:
                    sys_info = json.loads(row['system_info'])
                    os_str = f"{sys_info.get('os')} {sys_info.get('release')} ({sys_info.get('arch')})"
                    click.echo(f"  Ambiente:  {os_str} | Py {sys_info.get('python')}")
                except Exception: pass # <--- CORRIGIDO
        except Exception: pass # <--- CORRIGIDO

    # Exibição de Funções (Visão Geral)
    if profile_json:
        try:
            top_funcs = json.loads(profile_json)
            if top_funcs:
                click.echo(Fore.WHITE + "     📦 Funções Mais Pesadas (cProfile):")
                for i, func in enumerate(top_funcs[:3], 1): # Reduzi para 3 para focar nas linhas
                    clean_func = func.replace(work_dir, "").strip(os.sep)
                    func_color = Fore.YELLOW if "doxoade" in clean_func else Fore.WHITE
                    click.echo(f"       {i}. {func_color}{clean_func}{Style.RESET_ALL}")
        except Exception: pass

def _analyze_memory(row):
    """Análise detalhada de Memória RAM."""
    ram = row['peak_memory_mb'] or 0
    
    # Heurística de Memória
    status = "Leve"
    color = Fore.GREEN
    if ram > 500: status, color = "Pesado (Leak Risk?)", Fore.RED
    elif ram > 200: status, color = "Moderado", Fore.YELLOW
    
    click.echo(Fore.MAGENTA + "  🧠 [MEMÓRIA]")
    click.echo(f"     Peak RAM:  {_draw_bar(ram, 512, color=color)} {ram:.1f} MB")
    click.echo(f"     Status:    {color}{status}{Style.RESET_ALL}")

def _analyze_disk(row):
    """Análise detalhada de I/O de Disco."""
    read = row['io_read_mb'] or 0
    write = row['io_write_mb'] or 0
    total_io = read + write
    
    # Heurística de I/O
    io_type = "Baixo I/O"
    color = Fore.BLUE
    if total_io > 50: io_type, color = "Intenso (IO Bound)", Fore.RED
    elif total_io > 10: io_type, color = "Moderado", Fore.YELLOW

    click.echo(Fore.BLUE + "  💾 [DISCO I/O]")
    click.echo(f"     Leitura:   {read:.2f} MB")
    click.echo(f"     Escrita:   {write:.2f} MB")
    click.echo(f"     Total:     {color}{total_io:.2f} MB ({io_type}){Style.RESET_ALL}")

def _print_stats(cursor, command_filter):
    """Gera dashboard estatístico."""
    query = "SELECT command_name, duration_ms, cpu_percent, peak_memory_mb FROM command_history"
    if command_filter:
        query += f" WHERE LOWER(command_name) = '{command_filter.lower()}'"
        
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if not rows:
        click.echo(Fore.YELLOW + "Dados insuficientes para estatísticas.")
        return

    stats = {}
    for row in rows:
        cmd = row['command_name']
        if cmd not in stats:
            stats[cmd] = {'dur': [], 'cpu': [], 'ram': []}
        
        # [FIX] Só adiciona se não for None
        if row['duration_ms'] is not None: stats[cmd]['dur'].append(row['duration_ms'])
        if row['cpu_percent'] is not None: stats[cmd]['cpu'].append(row['cpu_percent'])
        if row['peak_memory_mb'] is not None: stats[cmd]['ram'].append(row['peak_memory_mb'])

    click.echo(Fore.CYAN + Style.BRIGHT + "\n=== 📈 MÉTRICAS DE PERFORMANCE (MÉDIAS) ===")
    click.echo(f"{'COMANDO':<15} | {'QTD':<5} | {'TEMPO(ms)':<10} | {'CPU(%)':<8} | {'RAM(MB)':<8}")
    click.echo("-" * 65)

    for cmd, data in sorted(stats.items(), key=lambda x: statistics.mean(x[1]['dur']) if x[1]['dur'] else 0, reverse=True):
        if not data['dur']: continue 
        
        count = len(data['dur'])
        avg_dur = statistics.mean(data['dur'])
        avg_cpu = statistics.mean(data['cpu']) if data['cpu'] else 0
        avg_ram = statistics.mean(data['ram']) if data['ram'] else 0
        
        color = Fore.WHITE
        if avg_dur > 5000: color = Fore.RED
        elif avg_dur > 1000: color = Fore.YELLOW
        
        click.echo(f"{color}{cmd:<15}{Style.RESET_ALL} | {count:<5} | {avg_dur:<10.0f} | {avg_cpu:<8.1f} | {avg_ram:<8.1f}")
    click.echo("-" * 65)

@click.command('telemetry')
@click.option('--limit', '-n', default=10, help="Número de registros.")
@click.option('--command', '-c', help="Filtra por comando.")
@click.option('--stats', '-s', is_flag=True, help="Estatísticas agregadas.")
@click.option('--processing', '-p', is_flag=True, help="Detalhes de CPU e Processos.")
@click.option('--memory', '-m', is_flag=True, help="Detalhes de Memória RAM.")
@click.option('--disk', '-d', is_flag=True, help="Detalhes de Disco I/O.")
@click.option('--verbose', '-v', is_flag=True, help="Verbosidade máxima (Ativa tudo).")
def telemetry(limit, command, stats, processing, memory, disk, verbose):
    """MaxTelemetry v2: Análise profunda de recursos."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if stats:
        _print_stats(cursor, command)
        conn.close()
        return

    # Se verbose estiver ativo, ativa todas as flags
    if verbose:
        processing = memory = disk = True

    # Se nenhuma flag for passada, mostra visão geral simples
    default_view = not any([processing, memory, disk])
    query = "SELECT * FROM command_history WHERE 1=1"
    params = []
    if command:
        query += " AND LOWER(command_name) = ?"
        params.append(command.lower())
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            click.echo(Fore.YELLOW + "Nenhum dado encontrado.")
            return

        click.echo(Fore.CYAN + Style.BRIGHT + "\n=== 📊 DOXOADE MAX TELEMETRY ===")
        
        for row in rows:
            # Extração segura de dados
            cmd = row['command_name'] or "unknown"
            ts = (row['timestamp'] or "")[:19]
            dur = row['duration_ms'] or 0.0
            status_symbol = f"{Fore.GREEN}✔" if row['exit_code'] == 0 else f"{Fore.RED}✘"
            
            # Cabeçalho do Card
            click.echo(f"\n{status_symbol} {Fore.WHITE}{ts} | {Style.BRIGHT}{cmd.upper()}{Style.RESET_ALL} ({dur:.0f}ms)")
            
            if default_view:
                # Visão Resumida
                cpu = row['cpu_percent'] or 0
                ram = row['peak_memory_mb'] or 0
                cpu_bar = _draw_bar(cpu, 100, width=10, color=Fore.YELLOW)
                ram_bar = _draw_bar(ram, 200, width=10, color=Fore.MAGENTA)
                click.echo(f"   CPU: {cpu_bar} {cpu}% | RAM: {ram_bar} {ram:.0f}MB")

            # Módulos de Detalhe
            if processing: _analyze_processing(row)
            if memory: _analyze_memory(row)
            if disk: _analyze_disk(row)
                
    finally:
        conn.close()