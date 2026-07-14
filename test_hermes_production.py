# -*- coding: utf-8 -*-
# test_hermes_production.py
"""
Teste de Produção Definitivo: Hermes v2 (HBC5 + HBC6 + HGD1)
Mede Python Puro vs Cold Start vs Warm Start.
"""
import sys
import time
from pathlib import Path

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path(__file__).resolve().parent
    modules_to_test = [
        'doxoade.tools.filesystem',
        'doxoade.tools.doxcolors',
        'doxoade.tools.error_info',
    ]
    
    print(f"\n{'═' * 70}")
    print(f"  🚀 HERMES V2 PRODUCTION TEST (Cold vs Warm vs Python)")
    print(f"{'═' * 70}")
    
    # ═══════════════════════════════════════════════════════════════════
    # FASE 1: BASELINE (Python Puro)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  {Fore.CYAN}▶ FASE 1: Medindo Baseline (Python Puro){Style.RESET_ALL}")
    baseline_times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        __import__(module_name)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        baseline_times[module_name] = elapsed_ms
        print(f"    {Fore.YELLOW}Python Puro:{Style.RESET_ALL} {module_name} em {elapsed_ms:.2f}ms")
        
        # Limpa o cache para o próximo teste
        del sys.modules[module_name]
    
    # ═══════════════════════════════════════════════════════════════════
    # FASE 2: COLD START (Hermes v2 - Primeiro Boot)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  {Fore.CYAN}▶ FASE 2: Cold Start (Hermes v2 - Parse + DFS + Cache Save){Style.RESET_ALL}")
    
    # Limpa o cache de disco para forçar o Cold Start
    import shutil
    cache_dir = project_root / '.doxoade' / 'hermes' / 'cache'
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    
    # Instala o Hook V2
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install, get_telemetry_report
    install(str(project_root))
    
    cold_times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        __import__(module_name)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        cold_times[module_name] = elapsed_ms
        print(f"    {Fore.RED}Cold Start:{Style.RESET_ALL} {module_name} em {elapsed_ms:.2f}ms")
    
    # ═══════════════════════════════════════════════════════════════════
    # FASE 3: WARM START (Hermes v2 - Disk Cache Hit)
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n  {Fore.CYAN}▶ FASE 3: Warm Start (Hermes v2 - Disk Cache Hit){Style.RESET_ALL}")
    
    warm_times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        __import__(module_name)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        warm_times[module_name] = elapsed_ms
        print(f"    {Fore.GREEN}Warm Start:{Style.RESET_ALL} {module_name} em {elapsed_ms:.2f}ms")
    
    # ═══════════════════════════════════════════════════════════════════
    # RELATÓRIO FINAL DE PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print(f"  📊 HERMES V2 PERFORMANCE REPORT")
    print(f"{'═' * 70}")
    print(f"  {'MÓDULO':<40} {'PYTHON':>10} {'COLD':>10} {'WARM':>10} {'SPD COLD':>10} {'SPD WARM':>10}")
    print(f"  {'─' * 90}")
    
    total_py = 0
    total_cold = 0
    total_warm = 0
    speedups_cold = []
    speedups_warm = []
    
    for module_name in modules_to_test:
        py = baseline_times[module_name]
        cold = cold_times[module_name]
        warm = warm_times[module_name]
        
        spd_cold = py / cold if cold > 0 else 0
        spd_warm = py / warm if warm > 0 else 0
        
        color_cold = Fore.GREEN if spd_cold >= 1.0 else Fore.YELLOW
        color_warm = Fore.GREEN if spd_warm >= 2.0 else Fore.CYAN if spd_warm >= 1.0 else Fore.YELLOW
        
        short_name = module_name if len(module_name) <= 40 else '...' + module_name[-37:]
        print(f"  {short_name:<40} {py:>8.2f}ms {cold:>8.2f}ms {warm:>8.2f}ms {color_cold}{spd_cold:>8.2f}×{Style.RESET_ALL} {color_warm}{spd_warm:>8.2f}×{Style.RESET_ALL}")
        
        total_py += py
        total_cold += cold
        total_warm += warm
        if spd_cold > 0: speedups_cold.append(spd_cold)
        if spd_warm > 0: speedups_warm.append(spd_warm)
    
    print(f"  {'─' * 90}")
    avg_cold = sum(speedups_cold) / len(speedups_cold) if speedups_cold else 0
    avg_warm = sum(speedups_warm) / len(speedups_warm) if speedups_warm else 0
    print(f"  {'TOTAL/MÉDIA':<40} {total_py:>8.2f}ms {total_cold:>8.2f}ms {total_warm:>8.2f}ms {Fore.CYAN}{avg_cold:>8.2f}×{Style.RESET_ALL} {Fore.GREEN}{avg_warm:>8.2f}×{Style.RESET_ALL}")
    
    if avg_warm >= 2.0:
        print(f"\n  {Fore.GREEN}🏆 VITÓRIA DECISIVA: Hermes Warm Start é {avg_warm:.2f}× mais rápido que Python Puro!{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}   O Marshal Cache + mmap Zero-Copy eliminou o gargalo do import machinery.{Style.RESET_ALL}")
    elif avg_warm >= 1.0:
        print(f"\n  {Fore.CYAN}✔ VITÓRIA: Hermes Warm Start é {avg_warm:.2f}× mais rápido que Python Puro.{Style.RESET_ALL}")
    else:
        print(f"\n  {Fore.YELLOW}⚠ Python Puro ainda vence no cenário atual. O gargalo pode ser I/O do cache_save.{Style.RESET_ALL}")
    
    print(f"\n{'═' * 70}\n")

if __name__ == '__main__':
    main()