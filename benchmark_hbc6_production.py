#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark Detalhado HBC6 - Validação de Produção
=================================================
Mede:
  1. Python Puro (baseline)
  2. Hermes Cold Start (sem cache)
  3. Hermes Warm Start (com cache)
  4. Telemetria detalhada do Motor C
  
Objetivo: Validar que o HBC6 está pronto para produção.
"""
import sys
import os
import time
import shutil
from pathlib import Path
from typing import Dict, List

def clear_all_caches():
    """Limpa TODOS os caches para forçar Cold Start."""
    project_root = Path(__file__).resolve().parent
    
    # 1. Cache do Hermes
    hermes_cache = project_root / '.doxoade' / 'hermes' / 'cache'
    if hermes_cache.exists():
        shutil.rmtree(hermes_cache)
        print(f"  ✔ Cache Hermes limpo")
    
    # 2. __pycache__ do Python
    pycache_cleaned = 0
    for pycache in project_root.rglob('__pycache__'):
        if 'hermes_systems' not in str(pycache):
            shutil.rmtree(pycache, ignore_errors=True)
            pycache_cleaned += 1
    
    if pycache_cleaned > 0:
        print(f"  ✔ {pycache_cleaned} __pycache__ limpos")

def measure_python_pure(module_name: str) -> float:
    """Mede o tempo do Python Puro (sem Hermes)."""
    # Desinstala o Hook do Hermes se estiver ativo
    import sys
    original_meta_path = sys.meta_path[:]
    sys.meta_path = [f for f in sys.meta_path if 'hermes' not in type(f).__module__.lower()]
    
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # Limpa submódulos
    keys_to_del = [k for k in sys.modules if k.startswith(module_name + '.')]
    for k in keys_to_del:
        del sys.modules[k]
    
    t0 = time.perf_counter_ns()
    __import__(module_name)
    t1 = time.perf_counter_ns()
    
    # Restaura o meta_path
    sys.meta_path = original_meta_path
    
    return (t1 - t0) / 1_000_000  # ms

def measure_hermes_v2(module_name: str, project_root: str) -> float:
    """Mede o tempo do Hermes V2 (Motor C)."""
    import sys
    
    # Limpa o módulo e submódulos
    if module_name in sys.modules:
        del sys.modules[module_name]
    keys_to_del = [k for k in sys.modules if k.startswith(module_name + '.')]
    for k in keys_to_del:
        del sys.modules[k]
    
    # Instala o Hook V2
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install
    install(str(project_root))
    
    t0 = time.perf_counter_ns()
    __import__(module_name)
    t1 = time.perf_counter_ns()
    
    return (t1 - t0) / 1_000_000  # ms

def run_benchmark():
    """Executa o benchmark completo."""
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path(__file__).resolve().parent
    
    # Módulos de teste (do menor para o maior)
    modules = [
        ('doxoade.tools.error_info', 'Pequeno (~4KB)'),
        ('doxoade.tools.doxcolors', 'Médio (~15KB)'),
        ('doxoade.tools.filesystem', 'Grande (~20KB)'),
    ]
    
    print(f"\n{'═' * 80}")
    print(f"  🔬 BENCHMARK DETALHADO HBC6 - VALIDAÇÃO DE PRODUÇÃO")
    print(f"{'═' * 80}")
    
    results = []
    
    for module_name, desc in modules:
        print(f"\n  {Fore.CYAN}▶ Testando: {module_name} ({desc}){Style.RESET_ALL}")
        
        # 1. Python Puro (baseline)
        clear_all_caches()
        py_time = measure_python_pure(module_name)
        print(f"    {Fore.YELLOW}Python Puro:{Style.RESET_ALL} {py_time:>8.2f} ms")
        
        # 2. Hermes Cold Start (Motor C + Cache Save)
        clear_all_caches()
        hermes_cold = measure_hermes_v2(module_name, project_root)
        print(f"    {Fore.RED}Hermes Cold:{Style.RESET_ALL} {hermes_cold:>8.2f} ms")
        
        # 3. Hermes Warm Start (Disk Cache Hit)
        hermes_warm = measure_hermes_v2(module_name, project_root)
        print(f"    {Fore.GREEN}Hermes Warm:{Style.RESET_ALL} {hermes_warm:>8.2f} ms")
        
        # Calcula speedups
        spd_cold = py_time / hermes_cold if hermes_cold > 0 else 0
        spd_warm = py_time / hermes_warm if hermes_warm > 0 else 0
        
        results.append({
            'module': module_name,
            'desc': desc,
            'python_ms': py_time,
            'hermes_cold_ms': hermes_cold,
            'hermes_warm_ms': hermes_warm,
            'speedup_cold': spd_cold,
            'speedup_warm': spd_warm,
        })
    
    # Relatório Final
    print(f"\n{'═' * 80}")
    print(f"  📊 RELATÓRIO DE PERFORMANCE HBC6")
    print(f"{'═' * 80}")
    print(f"  {'MÓDULO':<40} {'PYTHON':>10} {'COLD':>10} {'WARM':>10} {'SPD COLD':>10} {'SPD WARM':>10}")
    print(f"  {'─' * 90}")
    
    total_py = 0
    total_cold = 0
    total_warm = 0
    speedups_cold = []
    speedups_warm = []
    
    for r in results:
        short_name = r['module'] if len(r['module']) <= 40 else '...' + r['module'][-37:]
        
        color_cold = Fore.GREEN if r['speedup_cold'] >= 1.0 else Fore.YELLOW
        color_warm = Fore.GREEN if r['speedup_warm'] >= 2.0 else Fore.CYAN if r['speedup_warm'] >= 1.0 else Fore.YELLOW
        
        print(f"  {short_name:<40} {r['python_ms']:>8.2f}ms {r['hermes_cold_ms']:>8.2f}ms {r['hermes_warm_ms']:>8.2f}ms {color_cold}{r['speedup_cold']:>8.2f}×{Style.RESET_ALL} {color_warm}{r['speedup_warm']:>8.2f}×{Style.RESET_ALL}")
        
        total_py += r['python_ms']
        total_cold += r['hermes_cold_ms']
        total_warm += r['hermes_warm_ms']
        
        if r['speedup_cold'] > 0: speedups_cold.append(r['speedup_cold'])
        if r['speedup_warm'] > 0: speedups_warm.append(r['speedup_warm'])
    
    print(f"  {'─' * 90}")
    
    avg_cold = sum(speedups_cold) / len(speedups_cold) if speedups_cold else 0
    avg_warm = sum(speedups_warm) / len(speedups_warm) if speedups_warm else 0
    
    print(f"  {'TOTAL/MÉDIA':<40} {total_py:>8.2f}ms {total_cold:>8.2f}ms {total_warm:>8.2f}ms {Fore.CYAN}{avg_cold:>8.2f}×{Style.RESET_ALL} {Fore.GREEN}{avg_warm:>8.2f}×{Style.RESET_ALL}")
    
    # Veredito
    print(f"\n{'═' * 80}")
    if avg_warm >= 2.0:
        print(f"  {Fore.GREEN}🏆 VITÓRIA DECISIVA: Hermes Warm Start é {avg_warm:.2f}× mais rápido!{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}   O HBC6 está pronto para produção.{Style.RESET_ALL}")
    elif avg_warm >= 1.0:
        print(f"  {Fore.CYAN}✔ VITÓRIA: Hermes Warm Start é {avg_warm:.2f}× mais rápido.{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}   O HBC6 está pronto para produção.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.YELLOW}⚠ Python Puro ainda vence. Otimizações adicionais necessárias.{Style.RESET_ALL}")
    print(f"{'═' * 80}\n")
    
    return results

if __name__ == '__main__':
    run_benchmark()