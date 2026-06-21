# -*- coding: utf-8 -*-
"""
Meta-Análise Lazarus v1.0.
Objetivo: Avaliar a 'Taxa de Visão' do sistema de resgate.
Quem foi afetado, onde falhou e qual a precisão do diagnóstico.
"""
# [DOX-UNUSED] import re
from doxoade.database import get_db_connection
from doxoade.tools.doxcolors import Fore, Style

def run_meta_audit():
    print(f"{Fore.CYAN}🔬 [META-ANALYSIS] Avaliando Eficácia do Resgate...{Style.RESET_ALL}")
    conn = get_db_connection()
    
    # Analisa se o Lazarus encontrou arquivos reais ou ficou no "NATIVO"
    query = "SELECT file_path, COUNT(*) as qtd FROM open_incidents GROUP BY file_path"
    rows = conn.execute(query).fetchall()
    
    total = 0
    blind = 0
    
    print(f"\n  {Fore.WHITE}■ HISTÓRICO DE TRIANGULAÇÃO:{Style.RESET_ALL}")
    for r in rows:
        path = r['file_path']
        qtd = r['qtd']
        total += qtd
        if path == "NATIVO" or len(path) <= 1:
            blind += qtd
            color = Fore.RED
        else:
            color = Fore.GREEN
        print(f"    {color}• {path:<40} {Style.RESET_ALL} ➔ {qtd} eventos")

    accuracy = ((total - blind) / total * 100) if total > 0 else 100
    color_acc = Fore.GREEN if accuracy > 80 else Fore.RED
    print(f"\n  {Fore.WHITE}■ SCORE DE VISÃO DO LAZARUS:{Style.RESET_ALL}")
    print(f"    {color_acc}{accuracy:.1f}% de precisão na identificação de fontes.{Style.RESET_ALL}")
    
    conn.close()

if __name__ == "__main__":
    run_meta_audit()