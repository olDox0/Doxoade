#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# benchmark_hbc5_vs_hbc6.py
"""
Benchmark Forense: Python Puro vs HBC5 (C-Bridge) vs HBC6 (C-Bridge)
Atua como Profiler: O C-Bridge imprime telemetria de cada fase no stderr.
"""
import sys
import os
import time
import shutil
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO AUTÔNOMA DE AMBIENTE
# ═══════════════════════════════════════════════════════════════════
def setup_environment():
    """Configura o ambiente para funcionar tanto com 'python' quanto com 'doxoade run'."""
    project_root = Path(__file__).resolve().parent
    
    # Adiciona ao sys.path se necessário
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Configura variáveis de ambiente
    os.environ.setdefault('DOXOADE_PROJECT_ROOT', str(project_root))
    
    return project_root

def clear_all_caches():
    project_root = Path(__file__).resolve().parent
    cache_dir = project_root / '.doxoade' / 'hermes' / 'cache'
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    for pycache in project_root.rglob('__pycache__'):
        if 'venv' not in str(pycache) and '.doxoade' not in str(pycache):
            shutil.rmtree(pycache, ignore_errors=True)

def measure_python_pure(module_name):
    if module_name in sys.modules:
        del sys.modules[module_name]
    try:
        from doxoade.tools.hermes_systems.hermes_hook_v2 import uninstall
        uninstall()
    except: pass
    
    t0 = time.perf_counter()
    __import__(module_name)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

def measure_c_bridge(file_path, global_dict_path):
    """Chama o Motor C diretamente, bypassando o Hook do Python."""
    from doxoade.tools.hermes_systems.native import hermes_bridge
    t0 = time.perf_counter()
    code_obj = hermes_bridge.load_module(str(file_path), str(global_dict_path))
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

def run_benchmark():
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = setup_environment()
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    global_dict = project_root / '.doxoade' / 'hermes' / 'master.bin'
    
    # Garante que o master.bin (HGD1) existe para o C-Bridge
    if not global_dict.exists():
        print(f"{Fore.YELLOW}⚠ master.bin não encontrado. Gerando...{Style.RESET_ALL}")
        from doxoade.tools.hermes_systems.native.hermes_gd_builder import build_global_bin
        build_global_bin(str(project_root))
    
    targets = [
        ('doxoade.tools.error_info', 'Pequeno (~4KB)'),
        ('doxoade.tools.doxcolors', 'Médio (~15KB)'),
        ('doxoade.tools.filesystem', 'Grande (~20KB)'),
    ]
    
    print(f"\n{'═' * 90}")
    print(f"  🔬 BENCHMARK & PROFILER: Python vs HBC5 vs HBC6 (C-Bridge Raw)")
    print(f"{'═' * 90}\n")
    
    results = []
    
    for mod_name, desc in targets:
        print(f"  {Fore.CYAN}▶ Analisando: {mod_name} ({desc}){Style.RESET_ALL}")
        
        # 1. Python Puro
        clear_all_caches()
        py_cold = measure_python_pure(mod_name)
        py_warm = measure_python_pure(mod_name)
        
        # 2. HBC5 (C-Bridge)
        hbc5_file = build_dir / f"{mod_name}.hermes"
        h5_cold, h5_warm = 0, 0
        if hbc5_file.exists():
            clear_all_caches()
            print(f"    {Fore.CYAN}[HBC5 Cold]{Style.RESET_ALL} (Veja a telemetria C abaixo)")
            h5_cold = measure_c_bridge(hbc5_file, global_dict)
            print(f"    {Fore.CYAN}[HBC5 Warm]{Style.RESET_ALL}")
            h5_warm = measure_c_bridge(hbc5_file, global_dict)
        else:
            print(f"    {Fore.YELLOW}⚠ HBC5 (.hermes) não encontrado. Rode 'doxoade hermes build --hbc5 --all'{Style.RESET_ALL}")
            
        # 3. HBC6 (C-Bridge)
        hbc6_file = build_dir / f"{mod_name}.hbc6"
        h6_cold, h6_warm = 0, 0
        if hbc6_file.exists():
            clear_all_caches()
            print(f"    {Fore.GREEN}[HBC6 Cold]{Style.RESET_ALL} (Veja a telemetria C abaixo)")
            h6_cold = measure_c_bridge(hbc6_file, global_dict)
            print(f"    {Fore.GREEN}[HBC6 Warm]{Style.RESET_ALL}")
            h6_warm = measure_c_bridge(hbc6_file, global_dict)
        else:
            print(f"    {Fore.YELLOW}⚠ HBC6 (.hbc6) não encontrado.{Style.RESET_ALL}")
            
        results.append({
            'mod': mod_name,
            'py_warm': py_warm, 'h5_warm': h5_warm, 'h6_warm': h6_warm
        })
        print()
        
    # Relatório Final
    print(f"\n{'═' * 90}")
    print(f"  📊 RELATÓRIO COMPARATIVO (Warm Start - Cache Hit)")
    print(f"{'═' * 90}")
    print(f"  {'MÓDULO':<35} {'PYTHON':>10} {'HBC5':>10} {'HBC6':>10} {'H5 vs PY':>10} {'H6 vs PY':>10}")
    print(f"  {'─' * 85}")
    
    for r in results:
        short = r['mod'] if len(r['mod']) <= 35 else '...' + r['mod'][-32:]
        py = r['py_warm']
        h5 = r['h5_warm'] if r['h5_warm'] > 0 else None
        h6 = r['h6_warm'] if r['h6_warm'] > 0 else None
        
        h5_spd = f"{py/h5:.2f}×" if h5 else "N/A"
        h6_spd = f"{py/h6:.2f}×" if h6 else "N/A"
        
        h5_color = Fore.GREEN if h5 and h5 < py else Fore.RED if h5 and h5 > py else Fore.YELLOW
        h6_color = Fore.GREEN if h6 and h6 < py else Fore.RED if h6 and h6 > py else Fore.YELLOW
        
        h5_str = f"{h5:>8.2f}ms" if h5 else f"{'N/A':>10}"
        h6_str = f"{h6:>8.2f}ms" if h6 else f"{'N/A':>10}"
        
        print(f"  {short:<35} {py:>8.2f}ms {h5_str} {h6_str} {h5_color}{h5_spd:>10}{Style.RESET_ALL} {h6_color}{h6_spd:>10}{Style.RESET_ALL}")
        
    print(f"{'═' * 90}")
    print(f"  {Fore.CYAN}💡 DICA DE PROFILING:{Style.RESET_ALL} Leia os logs [HERMES-C] impressos acima.")
    print(f"     Eles mostram exatamente quantos ms o Motor C gastou em cada fase:")
    print(f"     - {Fore.YELLOW}disk_cache / mmap_open{Style.RESET_ALL}: Gargalo de I/O de disco.")
    print(f"     - {Fore.YELLOW}expand_strings{Style.RESET_ALL}: Custo do HBC5 (Dicionário HGD1).")
    print(f"     - {Fore.YELLOW}expand_bytecode{Style.RESET_ALL}: Custo do HBC6 (Expansão de Macros 0xC0).")
    print(f"     - {Fore.YELLOW}disk_save{Style.RESET_ALL}: Custo de serialização do Marshal no Cold Start.")
    print(f"{'═' * 90}\n")

if __name__ == '__main__':
    run_benchmark()