#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Bottleneck Detector - Identificador de Gargalos
========================================================
Mede cada fase do pipeline isoladamente para identificar onde está o overhead.
"""

import sys
import os
import time
import marshal
from pathlib import Path
from typing import Dict, Tuple

# Desabilita logs do Hermes para medição limpa
os.environ['HERMES_LOG_LEVEL'] = 'ERROR'

def test_python_pure_import(module_name: str) -> Dict[str, float]:
    """Mede import Python puro (baseline)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # Warm up
    __import__(module_name)
    del sys.modules[module_name]
    
    # Medição real
    start = time.perf_counter()
    __import__(module_name)
    elapsed = (time.perf_counter() - start) * 1000
    
    return {'total': elapsed, 'phase': 'Python Puro (import direto)'}

def test_hermes_c_bridge_raw(hermes_path: str, global_dict_path: str) -> Dict[str, float]:
    """Mede chamada direta ao Motor C (sem Hook)."""
    from doxoade.tools.hermes_systems.native import hermes_bridge
    
    # Warm up
    hermes_bridge.load_module(hermes_path, global_dict_path)
    
    # Medição real
    start = time.perf_counter()
    code_obj = hermes_bridge.load_module(hermes_path, global_dict_path)
    elapsed = (time.perf_counter() - start) * 1000
    
    return {'total': elapsed, 'phase': 'Motor C (chamada direta)'}

def test_marshal_load_only(marshal_data: bytes) -> Dict[str, float]:
    """Mede apenas o marshal.loads (baseline de deserialização)."""
    marshal.loads(marshal_data)
    
    start = time.perf_counter()
    code_obj = marshal.loads(marshal_data)
    elapsed = (time.perf_counter() - start) * 1000
    
    return {'total': elapsed, 'phase': 'Marshal.loads (baseline)'}

def test_file_read_only(file_path: str) -> Dict[str, float]:
    """Mede apenas leitura de arquivo (baseline de I/O)."""
    with open(file_path, 'rb') as f:
        f.read()
    
    start = time.perf_counter()
    with open(file_path, 'rb') as f:
        data = f.read()
    elapsed = (time.perf_counter() - start) * 1000
    
    return {'total': elapsed, 'size_bytes': len(data), 'phase': 'Leitura de arquivo (I/O puro)'}

def test_code_exec_only(code_obj) -> Dict[str, float]:
    """Mede apenas execução de code object (baseline de exec)."""
    from doxoade.tools.aegis.aegis_core import nexus_exec
    nexus_exec(code_obj, {})
    
    start = time.perf_counter()
    nexus_exec(code_obj, {})
    elapsed = (time.perf_counter() - start) * 1000
    
    return {'total': elapsed, 'phase': 'Execução de code object'}

def test_hermes_hook_overhead(module_name: str, project_root: str) -> Dict[str, float]:
    """Mede overhead do Hook V2 (MetaPathFinder)."""
    from doxoade.tools.hermes_systems.hermes_hook_v2 import install, uninstall
    
    install(project_root)
    
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    __import__(module_name)
    del sys.modules[module_name]
    
    start = time.perf_counter()
    __import__(module_name)
    elapsed = (time.perf_counter() - start) * 1000
    
    uninstall()
    
    return {'total': elapsed, 'phase': 'Hermes Hook V2 (com overhead)'}

def analyze_bottlenecks(module_name: str, project_root: str):
    """Analisa gargalos de um módulo específico."""
    from doxoade.tools.doxcolors import Fore, Style
    
    print(f"\n{'═' * 80}")
    print(f"  🔍 ANÁLISE DE GARGALOS: {module_name}")
    print(f"{'═' * 80}")
    
    build_dir = Path(project_root) / '.doxoade' / 'hermes' / 'build'
    global_dict = build_dir.parent / 'master.bin'
    hermes_file = build_dir / f"{module_name}.hbc6"
    
    results = []
    c_result = {'total': 0}
    hook_result = {'total': 0}
    
    # 1. Python Puro (baseline)
    print(f"\n  {Fore.CYAN}[1/6] Medindo Python Puro (baseline)...{Style.RESET_ALL}")
    py_result = test_python_pure_import(module_name)
    results.append(py_result)
    print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {py_result['phase']}: {py_result['total']:.3f}ms")
    
    # 2. Leitura de arquivo (I/O puro)
    if hermes_file.exists():
        print(f"\n  {Fore.CYAN}[2/6] Medindo I/O de disco (HBC6)...{Style.RESET_ALL}")
        io_result = test_file_read_only(str(hermes_file))
        results.append(io_result)
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {io_result['phase']}: {io_result['total']:.3f}ms ({io_result['size_bytes']} bytes)")
    
    # 3. Marshal.loads (baseline de deserialização)
    if hermes_file.exists():
        print(f"\n  {Fore.CYAN}[3/6] Medindo Marshal.loads (baseline)...{Style.RESET_ALL}")
        with open(hermes_file, 'rb') as f:
            data = f.read()
        offset = 10
        hrt_size = int.from_bytes(data[offset:offset+4], 'little')
        offset += 4 + hrt_size
        macro_dict_size = int.from_bytes(data[offset:offset+4], 'little')
        offset += 4 + macro_dict_size
        payload_size = int.from_bytes(data[offset:offset+4], 'little')
        offset += 4
        payload = data[offset:offset+payload_size]
        
        marshal_result = test_marshal_load_only(payload)
        results.append(marshal_result)
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {marshal_result['phase']}: {marshal_result['total']:.3f}ms")
    
    # 4. Motor C direto (sem Hook)
    if hermes_file.exists() and global_dict.exists():
        print(f"\n  {Fore.CYAN}[4/6] Medindo Motor C (chamada direta)...{Style.RESET_ALL}")
        c_result = test_hermes_c_bridge_raw(str(hermes_file), str(global_dict))
        results.append(c_result)
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {c_result['phase']}: {c_result['total']:.3f}ms")
    
    # 5. Hermes Hook V2 (com overhead)
    print(f"\n  {Fore.CYAN}[5/6] Medindo Hermes Hook V2 (com overhead)...{Style.RESET_ALL}")
    hook_result = test_hermes_hook_overhead(module_name, project_root)
    results.append(hook_result)
    print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {hook_result['phase']}: {hook_result['total']:.3f}ms")
    
    # 6. Execução de code object
    if hermes_file.exists() and global_dict.exists():
        print(f"\n  {Fore.CYAN}[6/6] Medindo execução de code object...{Style.RESET_ALL}")
        from doxoade.tools.hermes_systems.native import hermes_bridge
        code_obj = hermes_bridge.load_module(str(hermes_file), str(global_dict))
        exec_result = test_code_exec_only(code_obj)
        results.append(exec_result)
        print(f"    {Fore.GREEN}✓{Style.RESET_ALL} {exec_result['phase']}: {exec_result['total']:.3f}ms")
    
    # Relatório de gargalos
    print(f"\n{'═' * 80}")
    print(f"  📊 RELATÓRIO DE GARGALOS")
    print(f"{'═' * 80}")
    print(f"  {'FASE':<50} {'TEMPO':>10} {'% DO TOTAL':>12} {'STATUS':>15}")
    print(f"  {'─' * 87}")
    
    baseline = py_result['total']
    
    for r in results:
        pct = (r['total'] / baseline * 100) if baseline > 0 else 0
        
        if r['total'] > baseline * 2:
            status = f"{Fore.RED}⚠ GARGALO{Style.RESET_ALL}"
        elif r['total'] > baseline * 1.5:
            status = f"{Fore.YELLOW}⚠ OVERHEAD{Style.RESET_ALL}"
        else:
            status = f"{Fore.GREEN}✓ OK{Style.RESET_ALL}"
        
        phase_name = r['phase'][:48]
        print(f"  {phase_name:<50} {r['total']:>8.3f}ms {pct:>10.1f}% {status:>25}")
    
    # Diagnóstico final
    print(f"\n{'═' * 80}")
    print(f"  🎯 DIAGNÓSTICO")
    print(f"{'═' * 80}")
    
    if c_result['total'] > baseline * 3:
        print(f"  {Fore.RED}⚠ GARGALO CRÍTICO: Motor C está {c_result['total']/baseline:.1f}x mais lento que Python puro{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}→ Possíveis causas:{Style.RESET_ALL}")
        print(f"    • Overhead de chamada FFI (Python → C)")
        print(f"    • Expansão de bytecode muito lenta")
        print(f"    • Cache miss no dicionário global")
    elif hook_result['total'] > c_result['total'] * 2:
        print(f"  {Fore.YELLOW}⚠ OVERHEAD DO HOOK: Hook V2 adiciona {hook_result['total'] - c_result['total']:.1f}ms{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}→ Possíveis causas:{Style.RESET_ALL}")
        print(f"    • MetaPathFinder muito lento")
        print(f"    • Verificação de cache ineficiente")
    else:
        print(f"  {Fore.GREEN}✓ Sistema otimizado{Style.RESET_ALL}")
    
    print(f"\n{'═' * 80}\n")

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path(__file__).resolve().parent
    
    print(f"\n{'═' * 80}")
    print(f"  🔬 HERMES BOTTLENECK DETECTOR")
    print(f"  Identificador de Gargalos do Sistema de Carregamento")
    print(f"{'═' * 80}")
    
    modules_to_test = [
        'doxoade.tools.error_info',
        'doxoade.tools.doxcolors',
        'doxoade.tools.filesystem',
    ]
    
    for module in modules_to_test:
        analyze_bottlenecks(module, str(project_root))
    
    print(f"\n{Fore.GREEN}✓ Análise completa{Style.RESET_ALL}\n")

if __name__ == '__main__':
    main()