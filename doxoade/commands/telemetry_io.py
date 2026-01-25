# -*- coding: utf-8 -*-
"""
Telemetry IO v3.6 - Interface Nexus Gold.
Exibição detalhada de I/O e Memória.
"""
import os
import linecache
from click import echo
from colorama import Fore, Style

def draw_bar(value, max_val, width=10, color=Fore.GREEN):
    percent = min(1.0, value / max_val) if max_val > 0 else 0
    fill = int(width * percent)
    return f"{color}{'█' * fill}{Style.DIM}{'░' * (width - fill)}{Style.RESET_ALL}"

def render_resource_line(label, val, formatted_val, bar_color, max_ref, status):
    bar = draw_bar(val, max_ref, 10, bar_color)
    echo(f"   {Style.BRIGHT}{label:<10}{Style.NORMAL} {bar} {formatted_val:>10} │ {status}")

def render_disk_detail(read_mb, write_mb, status):
    """Renderiza I/O com distinção entre Leitura e Escrita."""
    from .telemetry_utils import format_bytes
    total = read_mb + write_mb
    bar = draw_bar(total, 50, 10, Fore.BLUE)
    
    r_str = f"{Fore.CYAN}R:{format_bytes(read_mb)}{Fore.RESET}"
    w_str = f"{Fore.YELLOW}W:{format_bytes(write_mb)}{Fore.RESET}"
    
    echo(f"   {Style.BRIGHT}{'DISK I/O':<10}{Style.NORMAL} {bar} {r_str} / {w_str} │ {status}")

def render_hot_lines(line_data):
    if not line_data: return
    echo(f"     {Fore.RED}🔥 Hot Lines (Gargalos):")
    for item in line_data[:3]:
        fname, lineno, hits = item['file'], item['line'], item['hits']
        content = linecache.getline(os.path.abspath(fname), lineno).strip()
        echo(f"       {Fore.YELLOW}{fname}:{lineno:<4}{Style.RESET_ALL} ({hits:>2} hits) > {Style.DIM}{content}")

def render_stats_table(stats):
    header = f"{'COMANDO':<15} | {'QTD':<5} | {'T-AVG(ms)':<10} | {'RAM(MB)':<8} | {'I/O R':<8} | {'I/O W':<8}"
    echo(Fore.CYAN + Style.BRIGHT + "\n=== 📈 DASHBOARD DE PERFORMANCE INDUSTRIAL ===")
    echo(header + "\n" + "-" * len(header))

    for cmd, data in sorted(stats.items(), key=lambda x: sum(x[1]['dur'])/len(x[1]['dur']), reverse=True):
        avg = lambda x: sum(x)/len(x) if x else 0
        echo(f"{Fore.WHITE}{cmd:<15}{Style.RESET_ALL} | {len(data['dur']):<5} | {avg(data['dur']):<10.0f} | "
             f"{avg(data['ram']):<8.1f} | {avg(data['io_r']):<8.2f} | {avg(data['io_w']):<8.2f}")