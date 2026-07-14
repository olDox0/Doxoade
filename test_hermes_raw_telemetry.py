# -*- coding: utf-8 -*-
# test_hermes_raw_telemetry.py
"""
Telemetria Raw: Isolamento de Gargalos Hermes V2 vs Python Puro
"""
import sys
import os
import time
import shutil
from pathlib import Path

def clear_caches():
    """Limpa todos os caches para forçar Cold Start."""
    project_root = Path(__file__).resolve().parent
    cache_dir = project_root / '.doxoade' / 'hermes' / 'cache'
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    
    # Limpa __pycache__ do Python para isolar o teste
    for pycache in project_root.rglob('__pycache__'):
        if 'hermes_systems' not in str(pycache):
            shutil.rmtree(pycache, ignore_errors=True)

def measure_python_pure(module_name):
    """Mede o tempo do Python Puro (com .pyc nativo)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    t0 = time.perf_counter_ns()
    __import__(module_name)
    t1 = time.perf_counter_ns()
    return (t1 - t0) / 1_000_000  # ms

def measure_hermes_v2(module_name, project_root):
    """Mede o tempo do Hermes V2 (Motor C)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # Instala o Hook V2 (sem threshold para este teste raw)
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install
    install(str(project_root))
    
    t0 = time.perf_counter_ns()
    __import__(module_name)
    t1 = time.perf_counter_ns()
    
    # Desinstala para não poluir o próximo teste
    from doxoade.tools.hermes_systems.hermes_hook_v2 import uninstall
    uninstall()
    
    return (t1 - t0) / 1_000_000  # ms

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path(__file__).resolve().parent
    modules = [
        'doxoade.tools.error_info',
        'doxoade.tools.doxcolors',
        'doxoade.tools.filesystem',
    ]
    
    print(f"\n{'═' * 80}")
    print(f"  🔬 HERMES V2 RAW TELEMETRY (Isolamento de Gargalos)")
    print(f"{'═' * 80}")
    
    results = []
    
    for mod in modules:
        print(f"\n  {Fore.CYAN}▶ Analisando: {mod}{Style.RESET_ALL}")
        
        # 1. Python Puro (Warm Start com .pyc)
        clear_caches()
        __import__(mod)  # Gera o .pyc
        py_warm = measure_python_pure(mod)
        print(f"    {Fore.YELLOW}Python Puro (.pyc Warm):{Style.RESET_ALL} {py_warm:>8.2f} ms")
        
        # 2. Hermes V2 Cold Start (Motor C + Cache Save)
        clear_caches()
        hermes_cold = measure_hermes_v2(mod, project_root)
        print(f"    {Fore.RED}Hermes V2 Cold Start   :{Style.RESET_ALL} {hermes_cold:>8.2f} ms")
        
        # 3. Hermes V2 Warm Start (Disk Cache Hit)
        hermes_warm = measure_hermes_v2(mod, project_root)
        print(f"    {Fore.GREEN}Hermes V2 Warm Start   :{Style.RESET_ALL} {hermes_warm:>8.2f} ms")
        
        results.append({
            'module': mod,
            'py_warm': py_warm,
            'hermes_cold': hermes_cold,
            'hermes_warm': hermes_warm
        })
    
    # Relatório Final
    print(f"\n{'═' * 80}")
    print(f"  📊 RELATÓRIO DE GARGALOS")
    print(f"{'═' * 80}")
    print(f"  {'MÓDULO':<40} {'PY .pyc':>10} {'H_COLD':>10} {'H_WARM':>10} {'VERDICT':>15}")
    print(f"  {'─' * 85}")
    
    for r in results:
        short_name = r['module'] if len(r['module']) <= 40 else '...' + r['module'][-37:]
        
        # Veredito: Qual é mais rápido no Warm Start?
        if r['hermes_warm'] < r['py_warm']:
            verdict = f"{Fore.GREEN}HERMES WINS{Style.RESET_ALL}"
        elif r['hermes_warm'] < r['py_warm'] * 1.5:
            verdict = f"{Fore.YELLOW}TIE (Threshold){Style.RESET_ALL}"
        else:
            verdict = f"{Fore.RED}PYTHON WINS{Style.RESET_ALL}"
        
        print(f"  {short_name:<40} {r['py_warm']:>8.2f}ms {r['hermes_cold']:>8.2f}ms {r['hermes_warm']:>8.2f}ms {verdict:>25}")
    
    print(f"\n{'═' * 80}\n")
    print(f"  {Fore.CYAN}💡 CONCLUSÃO:{Style.RESET_ALL} Módulos onde 'PYTHON WINS' devem ser bypassados")
    print(f"  pelo Smart Threshold no Hook V2 para usar o .pyc nativo do Python.\n")

if __name__ == '__main__':
    main()