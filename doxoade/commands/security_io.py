# -*- coding: utf-8 -*-
# doxoade/commands/security_io.py
"""
Security IO - Interface Forense (PASC-10).
"""
import os
from click import echo, progressbar
from colorama import Fore, Style

SEVERITY_MAP = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

def print_header(target: str, level: str):
    echo(Fore.CYAN + f"\n--- [SECURITY CHIEF] Auditoria: {target} ---")
    echo(Fore.WHITE + Style.DIM + f"   > Filtro de Severidade: {level}+")

def print_config_suggestion():
    """Sugestão automática conforme solicitado (PASC-4)."""
    echo(Fore.YELLOW + "\n[!] AVISO: Configuração do Doxoade não detectada neste projeto.")
    echo(Fore.GREEN + "    Sugerido: " + Style.BRIGHT + "doxoade setup-health" + Fore.RESET + " para inicializar protocolos.")

def get_progress_bar(items, label="Analisando"):
    return progressbar(
        items,
        label=Fore.WHITE + label,
        fill_char=Fore.CYAN + "█" + Fore.RESET,
        empty_char="░",
        show_pos=True,
        # Mostra o primeiro arquivo do lote para dar feedback visual
        item_show_func=lambda x: f"({os.path.basename(x[0])}...)" if x and isinstance(x, list) else ""
    )

def render_findings(findings: list, min_level: int, severity_map: dict):
    """Exibição coesa e informativa (MPoT-5.3)."""
    visible = [
        f for f in findings 
        if isinstance(f, dict) and severity_map.get(f.get('severity', 'LOW').upper(), 1) >= min_level
    ]
    if not visible:
        echo(Fore.GREEN + Style.BRIGHT + "\n[✔] Nenhuma vulnerabilidade crítica detectada.")
        return
    echo(Fore.RED + Style.BRIGHT + f"\n[ALERTA] {len(visible)} Vulnerabilidades Encontradas:")
    for f in visible:
        color = Fore.RED if f['severity'] in ['HIGH', 'CRITICAL'] else Fore.YELLOW
        echo(f"\n{color}■ [{f['tool']}] {f['severity']}: {f['message']}")
        echo(Fore.WHITE + f"  Local: {f['file']}:{f['line']}")
        if f.get('code'):
            echo(Fore.BLUE + f"  Trecho: {f['code'][:200]}...")
