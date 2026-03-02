# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/check_engine.py
"""Motor de Auditoria - Casa de Máquinas (PASC 8.5)."""
import sys
import re
import ast
import json
from typing import List, Dict, Any
from click import progressbar
from .check_state import CheckState
from ...tools.analysis import _get_code_snippet
def run_audit_engine(state: CheckState, io_manager, **kwargs):
    from ...probes.manager import ProbeManager
    from ...tools.memory_pool import finding_arena
    manager = ProbeManager(sys.executable, state.root)
    files = io_manager.resolve_files(kwargs.get('target_files'))
    cache = {} if kwargs.get('no_cache') else io_manager.load_cache()
    
    to_scan = _filter_by_cache(files, cache, io_manager, state, kwargs.get('no_cache'))
    
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for fp, cache_key, mtime, size in bar:
                results = _scan_single_file(fp, manager, kwargs)
                
                for res in results:
                    # --- INJEÇÃO JIT DE SNIPPET (v87.0) ---
                    # Buscamos o código na RAM (UFS) para não perder performance
                    snip = _get_code_snippet(res['file'], res.get('line', 0))
                    
                    arena_res = finding_arena.rent(
                        res['severity'], res['category'], res['message'], 
                        res['file'], res['line']
                    )
                    arena_res['snippet'] = snip # Acopla a visão ao achado
                    state.register_finding(arena_res)
                
                if mtime > 0 and not any(f.get('category') == 'SYSTEM' for f in results):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state)
    if not kwargs.get('no_cache'):
        io_manager.save_cache(cache)
def _scan_single_file(fp, manager, kwargs):
    """Executa as sondas respeitando o Full Power."""
    from ...tools.governor import governor
    # FIX: governor agora é visível aqui
    if governor.pace(file_path=fp, force=kwargs.get('full_power')):
        return [{'severity': 'INFO', 'category': 'SYSTEM', 'message': 'ALB_REDUCED', 'file': fp, 'line': 0}]
    
    findings = _run_syntax_check(fp, manager)
    if findings: return findings
    
    findings.extend(_run_static_probes(fp, manager))
    if not kwargs.get('fast'):
        findings.extend(_run_style_check(fp))
    return findings
def _run_syntax_check(f, manager):
    from ..check import _get_probe_path
    from ...tools.analysis import _get_code_snippet
    res = manager.execute(_get_probe_path('syntax_probe.py'), f)
    if not res["success"]:
        import re
        m = re.search(r'(?:line |:)(\d+)', res["error"])
        line_n = int(m.group(1)) if m else 1
        return [{
            'severity': 'CRITICAL', 'category': 'SYNTAX', 
            'message': f"Sintaxe: {res['error']}", 
            'file': f, 'line': line_n,
            'snippet': _get_code_snippet(f, line_n) # Injeção de snippet imediata para erros fatais
        }]
    return []
def _run_style_check(f):
    from radon.visitors import ComplexityVisitor
    from ...tools.streamer import ufs
    try:
        lines = ufs.get_lines(f)
        v = ComplexityVisitor.from_ast(ast.parse("".join(lines)))
        return [{'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f"Função '{func.name}' complexa (CC: {func.complexity}).", 'file': f, 'line': func.lineno} 
                for func in v.functions if func.complexity > 12]
    except Exception: return []
def _run_static_probes(f, manager):
    from ..check import _get_probe_path
    results = []
    res_pf = manager.execute(_get_probe_path('static_probe.py'), f)
    if res_pf["stdout"]:
        for line in res_pf["stdout"].splitlines():
            m = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            if m: results.append({'severity': 'WARNING', 'category': 'STYLE', 'message': m.group(3), 'file': f, 'line': int(m.group(2))})
    
    res_ht = manager.execute(_get_probe_path('hunter_probe.py'), f)
    try:
        data = json.loads(res_ht["stdout"]) # FIX: Usar json.loads do topo
        for d in (data if isinstance(data, list) else [data]):
            d['file'] = f
            results.append(d)
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
    return results
def _filter_by_cache(files, cache, io_manager, state, force_no_cache):
    to_scan = []
    for fp in files:
        mtime, _ = io_manager.get_file_metadata(fp)
        cache_key = fp.replace('\\', '/')
        c_entry = cache.get(cache_key)
        if not force_no_cache and c_entry and c_entry.get('mtime') == mtime:
            if not any(f.get('category') == 'SYSTEM' for f in c_entry.get('findings', [])):
                for f in c_entry.get('findings', []): state.register_finding(f)
                continue
        to_scan.append((fp, cache_key, mtime, 0))
    return to_scan
    
def _run_clone_detection(files, manager, state):
    from ..check import _get_probe_path
    res = manager.execute(_get_probe_path('clone_probe.py'), payload={'files': files})
    if res["success"] and res["stdout"]:
        try:
            clones = json.loads(res["stdout"])
            for c in clones: state.register_finding(c)
        except Exception as e:
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            
def _calculate_incident_stats(findings: List[Dict[str, Any]]) -> dict:
    """Especialista de contagem estatística (Expert-Split)."""
    from collections import defaultdict
    stats = defaultdict(lambda: defaultdict(int))
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat == 'SYSTEM': continue
        
        msg = f.get('message', '').lower()
        sub = "geral"
        if "f-string" in msg: sub = "f-string"
        elif "imported but unused" in msg: sub = "unused-import"
        elif "assigned to but never used" in msg: sub = "unused-variable"
        elif "except:" in msg or ("except" in msg and ":" in msg and "exception" not in msg): sub = "bare-except"
        stats[cat][sub] += 1
    return stats
    
def run_check_logic(path: str, state, *_args, **kwargs):
    """
    Bridge de Compatibilidade v93.0 (PASC-Omega).
    Permite que comandos externos (save, merge) usem o motor modular.
    """
    from .check_io import CheckIO
    from .check_filters import apply_filters
    from .check_refactor import analyze_refactor_opportunities
    # 1. Setup via novo GPS
    io = CheckIO(path)
    state = CheckState(
        root=io.project_root, 
        target_path=io.target_abs, 
        is_full_power=kwargs.get('full_power', False)
    )
    # 2. Execução do Motor Modular
    run_audit_engine(state, io, **kwargs)
    # 3. Inteligência e Crivo
    apply_filters(state, **kwargs)
    analyze_refactor_opportunities(state)
    # 4. Retorno no formato de dicionário esperado pelos comandos legados
    return {
        'summary': state.summary,
        'findings': state.findings,
        'alb_files': state.alb_files
    }
    
if __name__ == "__main__":
    main()