#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_benchmark_compare.py
"""
hermes_benchmark_compare.py — Benchmark Comparativo Mercury Systems
====================================================================
Compara Python Puro vs Mercury v2 (Cold Start vs Warm Start)
"""
import os
import sys
import time
import shutil
import importlib
from pathlib import Path
from typing import List, Dict


def clear_hermes_cache(project_root: str):
    """Remove todos os caches do Hermes para forçar Cold Start."""
    root = Path(project_root)
    cache_dir = root / '.doxoade' / 'hermes' / 'cache'
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    build_dir = root / '.doxoade' / 'hermes' / 'build'
    if build_dir.exists():
        for f in build_dir.rglob('*.hermes.cache'):
            f.unlink(missing_ok=True)


def benchmark_module_import(module_name: str, use_mercury: bool = False, project_root: str = None) -> float:
    """
    Mede o tempo de importação de um módulo.
    
    Args:
        module_name: Nome do módulo (ex: 'doxoade.cli')
        use_mercury: Se True, instala o Hook v2; se False, usa Python puro
        project_root: Raiz do projeto
    
    Returns:
        Tempo em milissegundos
    """
    # Remove do cache
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # Instala ou desinstala o Hook
    if use_mercury and project_root:
        try:
            from doxoade.tools.hermes_systems.hermes_hook_v2 import install as hermes_v2_install
            hermes_v2_install(project_root)
        except Exception:
            pass
    elif not use_mercury:
        try:
            from doxoade.tools.hermes_systems.hermes_hook_v2 import uninstall
            uninstall()
        except Exception:
            pass
    
    # Mede o tempo
    start = time.perf_counter_ns()
    try:
        importlib.import_module(module_name)
        end = time.perf_counter_ns()
        return (end - start) / 1_000_000  # ms
    except Exception as e:
        print(f"  ⚠ Falha ao importar {module_name}: {e}")
        return -1.0


def run_benchmark_compare(project_root: str, modules: List[str], runs: int = 3) -> List[Dict]:
    """
    Executa benchmark comparativo entre Python Puro e Mercury v2.
    
    Args:
        project_root: Raiz do projeto
        modules: Lista de módulos para testar
        runs: Número de execuções por cenário
    
    Returns:
        Lista de dicionários com resultados:
        [
            {
                'module': 'doxoade.cli',
                'python_ms': 123.45,
                'cold_ms': 98.76,
                'warm_ms': 45.32
            },
            ...
        ]
    """
    # Garante que o motor C está compilado
    try:
        from doxoade.tools.hermes_systems.native.hermes_bridge_builder import ensure_bridge_built
        ensure_bridge_built(project_root)
    except Exception as e:
        print(f"  ⚠ Falha ao compilar motor C: {e}")
    
    results = []
    
    for module in modules:
        print(f"\n  ▶ Benchmarking: {module}")
        
        # 1. Python Puro (baseline)
        times_py = []
        for i in range(runs):
            t = benchmark_module_import(module, use_mercury=False, project_root=project_root)
            if t > 0:
                times_py.append(t)
        avg_py = sum(times_py) / len(times_py) if times_py else 0
        
        # 2. Mercury Cold Start (limpa cache antes)
        times_cold = []
        for i in range(runs):
            clear_hermes_cache(project_root)
            t = benchmark_module_import(module, use_mercury=True, project_root=project_root)
            if t > 0:
                times_cold.append(t)
        avg_cold = sum(times_cold) / len(times_cold) if times_cold else 0
        
        # 3. Mercury Warm Start (cache já existe)
        times_warm = []
        for i in range(runs):
            t = benchmark_module_import(module, use_mercury=True, project_root=project_root)
            if t > 0:
                times_warm.append(t)
        avg_warm = sum(times_warm) / len(times_warm) if times_warm else 0
        
        results.append({
            'module': module,
            'python_ms': avg_py,
            'cold_ms': avg_cold,
            'warm_ms': avg_warm
        })
        
        print(f"    Python: {avg_py:>8.2f}ms | Cold: {avg_cold:>8.2f}ms | Warm: {avg_warm:>8.2f}ms")
    
    return results