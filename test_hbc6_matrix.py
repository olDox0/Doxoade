#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matriz de Testes Controlados HBC6 (Medição Isolada)
Elimina interferência de I/O externo para medir APENAS o Motor C.
"""
import sys
import os
import time
from pathlib import Path

# Força logs do Motor C para coletar dados
os.environ['HERMES_VERBOSE'] = '1'

def measure_c_bridge_isolated(file_path, global_dict_path):
    """Mede APENAS a chamada ao Motor C, sem interferência de I/O externo."""
    from doxoade.tools.hermes_systems.native import hermes_bridge
    
    # 1. Warm up (garante que o módulo Python está carregado e o Buffer Pool alocado)
    hermes_bridge.load_module(str(file_path), str(global_dict_path))
    
    # 2. Medição pura (sem clear_caches no meio!)
    t0 = time.perf_counter()
    hermes_bridge.load_module(str(file_path), str(global_dict_path))
    t1 = time.perf_counter()
    
    return (t1 - t0) * 1000

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path(__file__).resolve().parent
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    global_dict = project_root / '.doxoade' / 'hermes' / 'master.bin'
    
    targets = [
        ('doxoade.tools.error_info', 'Pequeno (~4KB)'),
        ('doxoade.tools.doxcolors', 'Médio (~15KB)'),
        ('doxoade.tools.filesystem', 'Grande (~20KB)'),
    ]
    
    print(f"\n{'═' * 90}")
    print(f"  🔬 MATRIZ DE TESTES CONTROLADOS HBC6 (Medição Isolada)")
    print(f"{'═' * 90}\n")
    print(f"  {Fore.CYAN}Nota: O clear_caches foi removido da medição para evitar{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}falsos positivos causados pelo I/O do Windows/Antivírus.{Style.RESET_ALL}\n")
    
    for mod_name, desc in targets:
        print(f"{'─' * 90}")
        print(f"  {Fore.MAGENTA}▶ ALVO: {mod_name} ({desc}){Style.RESET_ALL}")
        print(f"{'─' * 90}")
        
        hbc6_file = build_dir / f"{mod_name}.hbc6"
        if not hbc6_file.exists():
            print(f"    {Fore.RED}✘ Arquivo .hbc6 não encontrado. Rode o build HBC6 primeiro.{Style.RESET_ALL}\n")
            continue
            
        print(f"    Tamanho do arquivo: {hbc6_file.stat().st_size / 1024:.2f} KB")
        print(f"    {Fore.YELLOW}[Medição Isolada do Motor C - 3 execuções]{Style.RESET_ALL}")
        
        # Mede 3 vezes e pega a média para estabilidade
        times = []
        for i in range(3):
            elapsed = measure_c_bridge_isolated(hbc6_file, global_dict)
            times.append(elapsed)
            
        avg_time = sum(times) / len(times)
        min_time = min(times)
        
        print(f"    {Fore.GREEN}→ Tempo Médio: {avg_time:.2f} ms (Mínimo: {min_time:.2f} ms){Style.RESET_ALL}\n")
        
    print(f"{'═' * 90}")
    print(f"  {Fore.CYAN}💡 CONCLUSÃO:{Style.RESET_ALL}")
    print(f"     Se os tempos acima estiverem na faixa de 5-40ms, o Motor C está saudável.")
    print(f"     Qualquer valor > 100ms indica um problema real no pipeline C.")
    print(f"{'═' * 90}\n")

if __name__ == '__main__':
    main()