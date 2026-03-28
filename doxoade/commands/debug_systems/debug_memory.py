# -*- coding: utf-8 -*-
"""
Debug Memory Engine - MPoT-18.
Autópsia Forense de Memória (Composição, Tracebacks e Referências).
"""
import sys
import gc
import tracemalloc
import linecache
from collections import defaultdict

def get_memory_composition(limit: int = 20) -> list:
    """Tira um raio-x dos objetos vivos na memória (shallow size)."""
    gc.collect()  # Força coleta de lixo inativo
    objects = gc.get_objects()
    
    stats = defaultdict(lambda: {"count": 0, "total_bytes": 0})
    
    for obj in objects:
        try:
            obj_type = type(obj).__name__
            # Ignora os módulos e funções do próprio interpretador para focar nos dados
            if obj_type in ('module', 'function', 'builtin_function_or_method', 'wrapper_descriptor', 'method_descriptor', 'frame', 'code'):
                continue
            
            stats[obj_type]["count"] += 1
            stats[obj_type]["total_bytes"] += sys.getsizeof(obj)
        except Exception:
            pass
            
    # Ordena pelo tamanho total ocupado
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total_bytes"], reverse=True)
    
    results =[]
    for obj_type, data in sorted_stats[:limit]:
        results.append({
            "type": obj_type,
            "count": data["count"],
            "size_kb": round(data["total_bytes"] / 1024, 2)
        })
    return results

def get_allocation_tracebacks(snapshot: tracemalloc.Snapshot, limit: int = 5) -> list:
    """Obtém a árvore genealógica (Call Chain) das maiores alocações."""
    top_stats = snapshot.statistics('traceback')
    
    results =[]
    for stat in top_stats[:limit]:
        trace_chain =[]
        for frame in stat.traceback:
            fname = frame.filename
            norm_fname = fname.lower().replace('\\', '/')
            
            # Filtra o próprio sistema de importação do Python e a sonda do Doxoade
            if "<frozen" in fname or "importlib" in fname or "doxoade" in norm_fname or "<sandbox>" in fname:
                continue
                
            code_line = linecache.getline(fname, frame.lineno).strip()
            trace_chain.append({
                "file": fname,
                "line": frame.lineno,
                "code": code_line
            })
            
        if trace_chain:
            results.append({
                "size_kb": round(stat.size / 1024, 2),
                "count": stat.count,
                "traceback": trace_chain
            })
            
    return results