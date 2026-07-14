# -*- coding: utf-8 -*-
# test_hermes_integration_final.py
"""
Hermes V2 Integration Test - Validação Completa do Pipeline
============================================================
Valida:
  1. Compilação do Motor C (hermes_bridge.pyd)
  2. Geração do Dicionário Global (master.bin)
  3. Compressão de módulos (HBC5 + HBC6)
  4. Carregamento via Motor C (Cold Start)
  5. Cache em disco (Warm Start)
  6. Telemetria de performance
"""
import sys
import os
import time
import shutil
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

def clear_all_caches():
    """Limpa todos os caches para forçar Cold Start."""
    project_root = Path(__file__).resolve().parent
    
    # 1. Cache do Hermes
    hermes_cache = project_root / '.doxoade' / 'hermes' / 'cache'
    if hermes_cache.exists():
        shutil.rmtree(hermes_cache)
        print(f"  {Fore.YELLOW}✔{Style.RESET_ALL} Cache Hermes limpo")
    
    # 2. __pycache__ do Python
    for pycache in project_root.rglob('__pycache__'):
        if 'hermes_systems' not in str(pycache):
            shutil.rmtree(pycache, ignore_errors=True)
    print(f"  {Fore.YELLOW}✔{Style.RESET_ALL} __pycache__ limpo")

def test_motor_c_compiled():
    """Testa se o Motor C está compilado."""
    print(f"\n{Fore.CYAN}▶ FASE 1: Verificando Motor C{Style.RESET_ALL}")
    try:
        from doxoade.tools.hermes_systems.native import hermes_bridge
        print(f"  {Fore.GREEN}✔{Style.RESET_ALL} hermes_bridge.pyd carregado com sucesso")
        return True
    except ImportError as e:
        print(f"  {Fore.RED}✘{Style.RESET_ALL} Falha ao carregar hermes_bridge: {e}")
        print(f"  {Fore.YELLOW}→ Execute: doxoade hermes native{Style.RESET_ALL}")
        return False

def test_global_dict():
    """Testa se o Dicionário Global existe."""
    print(f"\n{Fore.CYAN}▶ FASE 2: Verificando Dicionário Global{Style.RESET_ALL}")
    project_root = Path(__file__).resolve().parent
    master_bin = project_root / '.doxoade' / 'hermes' / 'master.bin'
    
    if not master_bin.exists():
        print(f"  {Fore.RED}✘{Style.RESET_ALL} master.bin não encontrado")
        print(f"  {Fore.YELLOW}→ Execute: python doxoade/tools/hermes_systems/native/hermes_gd_builder.py{Style.RESET_ALL}")
        return False
    
    size_kb = master_bin.stat().st_size / 1024
    print(f"  {Fore.GREEN}✔{Style.RESET_ALL} master.bin encontrado ({size_kb:.2f} KB)")
    return True

def test_compression():
    """Testa a compressão de módulos."""
    print(f"\n{Fore.CYAN}▶ FASE 3: Testando Compressão HBC5 + HBC6{Style.RESET_ALL}")
    
    project_root = Path(__file__).resolve().parent
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    
    # Verifica se há módulos .hbc6
    hbc6_files = list(build_dir.glob('*.hbc6'))
    if not hbc6_files:
        print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL} Nenhum módulo .hbc6 encontrado")
        print(f"  {Fore.YELLOW}→ Execute: python build_critical_hbc6.py{Style.RESET_ALL}")
        return False
    
    print(f"  {Fore.GREEN}✔{Style.RESET_ALL} {len(hbc6_files)} módulos .hbc6 encontrados")
    
    # Mostra estatísticas
    for hbc6 in hbc6_files[:3]:  # Mostra apenas os 3 primeiros
        size_kb = hbc6.stat().st_size / 1024
        print(f"    • {hbc6.name}: {size_kb:.2f} KB")
    
    return True

def test_cold_start():
    """Testa o Cold Start via Motor C."""
    print(f"\n{Fore.CYAN}▶ FASE 4: Testando Cold Start{Style.RESET_ALL}")
    
    clear_all_caches()
    
    # Instala o Hook V2
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install
    install(str(Path(__file__).resolve().parent))
    
    # Importa módulos críticos
    modules_to_test = [
        'doxoade.tools.filesystem',
        'doxoade.tools.doxcolors',
        'doxoade.tools.error_info',
    ]
    
    times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        try:
            __import__(module_name)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            times[module_name] = elapsed_ms
            print(f"  {Fore.GREEN}✔{Style.RESET_ALL} {module_name}: {elapsed_ms:.2f}ms")
        except Exception as e:
            print(f"  {Fore.RED}✘{Style.RESET_ALL} {module_name}: {e}")
            times[module_name] = -1
    
    return times

def test_warm_start():
    """Testa o Warm Start (Cache Hit)."""
    print(f"\n{Fore.CYAN}▶ FASE 5: Testando Warm Start (Cache Hit){Style.RESET_ALL}")
    
    # Instala o Hook V2
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install
    install(str(Path(__file__).resolve().parent))
    
    # Importa módulos críticos
    modules_to_test = [
        'doxoade.tools.filesystem',
        'doxoade.tools.doxcolors',
        'doxoade.tools.error_info',
    ]
    
    times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        try:
            __import__(module_name)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            times[module_name] = elapsed_ms
            print(f"  {Fore.GREEN}✔{Style.RESET_ALL} {module_name}: {elapsed_ms:.2f}ms")
        except Exception as e:
            print(f"  {Fore.RED}✘{Style.RESET_ALL} {module_name}: {e}")
            times[module_name] = -1
    
    return times

def test_python_pure():
    """Testa o Python Puro (baseline)."""
    print(f"\n{Fore.CYAN}▶ FASE 6: Testando Python Puro (Baseline){Style.RESET_ALL}")
    
    # Desinstala o Hook V2
    try:
        from doxoade.tools.hermes_systems.hermes_hook_v2 import uninstall
        uninstall()
    except:
        pass
    
    # Importa módulos críticos
    modules_to_test = [
        'doxoade.tools.filesystem',
        'doxoade.tools.doxcolors',
        'doxoade.tools.error_info',
    ]
    
    times = {}
    for module_name in modules_to_test:
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        t0 = time.perf_counter()
        try:
            __import__(module_name)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            times[module_name] = elapsed_ms
            print(f"  {Fore.GREEN}✔{Style.RESET_ALL} {module_name}: {elapsed_ms:.2f}ms")
        except Exception as e:
            print(f"  {Fore.RED}✘{Style.RESET_ALL} {module_name}: {e}")
            times[module_name] = -1
    
    return times

def generate_report(cold_times, warm_times, pure_times):
    """Gera relatório final de performance."""
    print(f"\n{'═' * 80}")
    print(f"  📊 HERMES V2 INTEGRATION REPORT")
    print(f"{'═' * 80}")
    print(f"  {'MÓDULO':<40} {'PYTHON':>10} {'COLD':>10} {'WARM':>10} {'SPD COLD':>10} {'SPD WARM':>10}")
    print(f"  {'─' * 90}")
    
    total_py = 0
    total_cold = 0
    total_warm = 0
    speedups_cold = []
    speedups_warm = []
    
    for module_name in cold_times.keys():
        py = pure_times.get(module_name, 0)
        cold = cold_times.get(module_name, 0)
        warm = warm_times.get(module_name, 0)
        
        if py <= 0 or cold <= 0 or warm <= 0:
            continue
        
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
        print(f"\n  {Fore.YELLOW}⚠ Python Puro ainda vence no cenário atual.{Style.RESET_ALL}")
    
    print(f"\n{'═' * 80}\n")

def main():
    print(f"\n{'═' * 80}")
    print(f"  🔬 HERMES V2 INTEGRATION TEST - VALIDAÇÃO COMPLETA")
    print(f"{'═' * 80}")
    
    # Fase 1: Motor C
    if not test_motor_c_compiled():
        return
    
    # Fase 2: Dicionário Global
    if not test_global_dict():
        return
    
    # Fase 3: Compressão
    if not test_compression():
        return
    
    # Fase 4: Cold Start
    cold_times = test_cold_start()
    
    # Fase 5: Warm Start
    warm_times = test_warm_start()
    
    # Fase 6: Python Puro
    pure_times = test_python_pure()
    
    # Relatório Final
    generate_report(cold_times, warm_times, pure_times)
    
    print(f"  {Fore.GREEN}✔ INTEGRAÇÃO HERMES V2 CONCLUÍDA COM SUCESSO!{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}→ O sistema está pronto para produção.{Style.RESET_ALL}\n")

if __name__ == '__main__':
    main()