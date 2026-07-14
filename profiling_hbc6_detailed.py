#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# profiling_hbc6_detailed.py
"""
Profiling Cirúrgico: Micro-Timers do Motor C
"""
import sys
import os
import time
import shutil
from pathlib import Path

def clear_caches():
    project_root = Path(__file__).resolve().parent
    cache_dir = project_root / '.doxoade' / 'hermes' / 'cache'
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    # Ativa micro-timers
    os.environ['HERMES_VERBOSE'] = '1'
    
    project_root = Path(__file__).resolve().parent
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    global_dict = project_root / '.doxoade' / 'hermes' / 'master.bin'
    
    modules = [
        'doxoade.tools.error_info',
        'doxoade.tools.doxcolors',
        'doxoade.tools.filesystem',
    ]
    
    print(f"\n{'═' * 90}")
    print(f"  🔬 PROFILING CIRÚRGICO: Micro-Timers do Motor C")
    print(f"{'═' * 90}\n")
    
    from doxoade.tools.hermes_systems.native import hermes_bridge
    
    for mod_name in modules:
        print(f"{Fore.CYAN}▶ {mod_name}{Style.RESET_ALL}")
        
        # Cold Start (força parse + expand)
        clear_caches()
        hbc6_file = build_dir / f"{mod_name}.hbc6"
        
        if not hbc6_file.exists():
            print(f"  {Fore.RED}✘ Arquivo .hbc6 não encontrado{Style.RESET_ALL}\n")
            continue
        
        print(f"  {Fore.YELLOW}[COLD START - Veja micro-timers abaixo]{Style.RESET_ALL}")
        t0 = time.perf_counter()
        code_obj = hermes_bridge.load_module(str(hbc6_file), str(global_dict))
        t1 = time.perf_counter()
        
        print(f"  {Fore.GREEN}Total Cold Start: {(t1-t0)*1000:.2f}ms{Style.RESET_ALL}")
        
        # Warm Start (cache hit)
        print(f"\n  {Fore.YELLOW}[WARM START - Cache Hit]{Style.RESET_ALL}")
        t0 = time.perf_counter()
        code_obj = hermes_bridge.load_module(str(hbc6_file), str(global_dict))
        t1 = time.perf_counter()
        
        print(f"  {Fore.GREEN}Total Warm Start: {(t1-t0)*1000:.2f}ms{Style.RESET_ALL}\n")
    
    print(f"{'═' * 90}")
    print(f"  {Fore.CYAN}💡 ANALISE OS MICRO-TIMERS ACIMA:{Style.RESET_ALL}")
    print(f"     - Se 'Scan O(N)' > 10000 cycles → Otimizar loop de cálculo de tamanho")
    print(f"     - Se 'Expansion loop' > 50000 cycles → Usar SIMD/buffer pool")
    print(f"     - Se 'PyBytes_Alloc' > 20000 cycles → Pré-alocar buffer global")
    print(f"{'═' * 90}\n")

if __name__ == '__main__':
    main()