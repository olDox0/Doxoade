# -*- coding: utf-8 -*-
"""
Debug IO - Interface Forense (PASC-10).
"""
import os
from click import echo
from colorama import Fore, Style

def print_debug_header(script: str, mode: str = "DEBUG"):
    color = Fore.CYAN if mode == "VIGILÂNCIA" else Fore.BLUE
    echo(color + Style.BRIGHT + f"🔍 [ {mode} ] {Fore.WHITE}Analisando: {os.path.basename(script)}")

def render_variable_table(variables: dict):
    """Renderização simétrica Chief-Gold (MPoT-4)."""
    if not variables: return
    echo(Fore.CYAN + "\n[ ESTADO DAS VARIÁVEIS ]")
    for k, v in variables.items():
        val = str(v).replace('\n', ' ')
        if len(val) > 70: val = val[:67] + "..."
        echo(f"   {Fore.BLUE}{k:<18} {Fore.WHITE}│ {Style.DIM}{val}")

def report_crash(data: dict, script: str):
    """Relatório Lazarus de falha em runtime."""
    echo(f"\n{Fore.RED}{Style.BRIGHT}🚨 [ CRASH DETECTADO ]")
    echo(f"{Fore.RED}Erro: {data.get('error', 'Erro desconhecido')}")
    echo(f"{Fore.YELLOW}Local: L{data.get('line', '??')} em {os.path.basename(script)}")
    render_variable_table(data.get('variables'))
    echo(Fore.RED + "\n--- TRACEBACK ---")
    echo(data.get('traceback', 'Nenhum rastro disponível.'))