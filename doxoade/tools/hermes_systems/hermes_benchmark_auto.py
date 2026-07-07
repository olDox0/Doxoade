# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_benchmark_auto.py
"""
Hermes Benchmark Auto-Update v2.0
==================================
Executa benchmark e atualiza métricas de performance automaticamente.
Usado para alimentar o cache de preload inteligente.
"""
import sys
import time
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

def benchmark_and_update(modules: List[str], runs: int = 3) -> Dict:
    """
    Executa benchmark e atualiza métricas de performance.
    
    Args:
        modules: Lista de módulos para benchmark
        runs: Número de execuções por cenário
    
    Returns:
        Dict com resultados
    """
    from doxoade.tools.hermes_systems.hermes_auto_preload import update_metrics
    from doxoade.tools.hermes_systems.hermes_benchmark_compare import run_benchmark_compare
    
    print(f"\n{'═' * 70}")
    print(f"  🔬 MERCURY BENCHMARK AUTO-UPDATE")
    print(f"{'═' * 70}")
    print(f"  Módulos: {len(modules)}")
    print(f"  Runs: {runs} por cenário\n")
    
    # Executa benchmark
    results = run_benchmark_compare(str(PROJECT_ROOT), modules, runs=runs)
    
    # Atualiza métricas
    print(f"\n  📊 Atualizando métricas de performance...")
    for result in results:
        module_name = result['module']
        python_time = result['python_ms']
        mercury_time = result['warm_ms']  # Usa warm start para métricas
        
        update_metrics(str(PROJECT_ROOT), module_name, python_time, mercury_time)
        
        speedup = python_time / mercury_time if mercury_time > 0 else 1.0
        status = "✔" if speedup >= 1.2 else "⚠"
        print(f"    {status} {module_name}: {speedup:.2f}×")
    
    print(f"\n{'═' * 70}")
    print(f"  ✔ Métricas atualizadas com sucesso!")
    print(f"{'═' * 70}\n")
    
    return results


def benchmark_critical_modules(runs: int = 3) -> Dict:
    """Executa benchmark nos módulos críticos padrão."""
    critical_modules = [
        "doxoade.cli",
        "doxoade.tools.vulcan.forge",
        "doxoade.tools.hermes_systems.hermes_loader",
        "doxoade.core_database",
        "doxoade.tools.filesystem",
        "doxoade.tools.doxcolors",
        "doxoade.tools.error_info",
        "doxoade.tools.git",
        "doxoade.rescue",
        "doxoade.tools.aegis.nexus_db",
        "doxoade.tools.alexandria.engine",
        "doxoade.tools.telemetry_tools.logger",
        "doxoade.tools.aegis.aegis_utils",
        "doxoade.tools.display",
        "doxoade.tools.aegis.aegis_core",
        "doxoade.tools.analysis",
        "doxoade.tools.streamer",
        "doxoade.tools.vulcan.opt_cache",
        "doxoade.tools.vulcan.lib_optimizer",
        "doxoade.tools.vulcan.meta_finder",
    ]
    
    return benchmark_and_update(critical_modules, runs=runs)


if __name__ == "__main__":
    import sys
    
    # Se passou argumentos, usa como módulos
    if len(sys.argv) > 1:
        modules = sys.argv[1:]
        benchmark_and_update(modules)
    else:
        # Usa módulos críticos padrão
        benchmark_critical_modules()