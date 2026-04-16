# doxoade/doxoade/commands/check_systems/check_engine.py
"""Motor de Auditoria - Casa de Máquinas (PASC 8.5)."""
import os
import sys
import re
import ast
import json
from typing import List, Dict, Any
from click import progressbar
from .check_state import CheckState
from .check_utils import _calculate_incident_stats
from doxoade.tools.analysis import _get_code_snippet
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.filesystem import get_file_metadata

def run_audit_engine(state: CheckState, io_manager, **kwargs):
    from ...probes.manager import ProbeManager
    from doxoade.tools.memory_pool import finding_arena
    manager = ProbeManager(sys.executable, state.root)
    files = io_manager.resolve_files(kwargs.get('target_files'))
    cache = {} if kwargs.get('no_cache') else io_manager.load_cache()
    to_scan = _filter_by_cache(files, cache, io_manager, state, kwargs.get('no_cache'))
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for fp, cache_key, mtime, size in bar:
                results = _scan_single_file(fp, manager, kwargs)
                for res in results:
                    snip = _get_code_snippet(res['file'], res.get('line', 0))
                    arena_res = finding_arena.rent(res['severity'], res['category'], res['message'], res['file'], res['line'])
                    arena_res['snippet'] = snip
                    state.register_finding(arena_res)
                if mtime > 0 and (not any((f.get('category') == 'SYSTEM' for f in results))):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state)
    if not kwargs.get('no_cache'):
        io_manager.save_cache(cache)

def _scan_single_file(fp, manager, kwargs):
    """Executa as sondas respeitando o Full Power."""
    from doxoade.tools.governor import governor
    if governor.pace(file_path=fp, force=kwargs.get('full_power')):
        return [{'severity': 'INFO', 'category': 'SYSTEM', 'message': 'ALB_REDUCED', 'file': fp, 'line': 0}]
    if fp.endswith(('.c', '.cpp', '.h', '.hpp')):
        return _run_c_cpp_checks(fp)
    findings = _run_syntax_check(fp, manager)
    if findings:
        return findings
    findings.extend(_run_static_probes(fp, manager))
    if not kwargs.get('fast'):
        findings.extend(_run_style_check(fp))
    return findings

def _run_syntax_check(f, manager):
    from ..check import _get_probe_path
    from doxoade.tools.analysis import _get_code_snippet
    res = manager.execute(_get_probe_path('syntax_probe.py'), f)
    if not res['success']:
        import re
        m = re.search('(?:line |:)(\\d+)', res['error'])
        line_n = int(m.group(1)) if m else 1
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f'Sintaxe: {res['error']}', 'file': f, 'line': line_n, 'snippet': _get_code_snippet(f, line_n)}]
    return []

def _run_style_check(f):
    from radon.visitors import ComplexityVisitor
    from doxoade.tools.streamer import ufs
    try:
        lines = ufs.get_lines(f)
        v = ComplexityVisitor.from_ast(ast.parse(''.join(lines)))
        return [{'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f"Função '{func.name}' complexa (CC: {func.complexity}).", 'file': f, 'line': func.lineno} for func in v.functions if func.complexity > 12]
    except Exception:
        return []

def _run_static_probes(f, manager):
    from ..check import _get_probe_path
    results = []
    res_pf = manager.execute(_get_probe_path('static_probe.py'), f)
    if res_pf['stdout']:
        for line in res_pf['stdout'].splitlines():
            m = re.match('^(.+):(\\d+):(?:\\d+):? (.+)$', line)
            if m:
                results.append({'severity': 'WARNING', 'category': 'STYLE', 'message': m.group(3), 'file': f, 'line': int(m.group(2))})
    res_ht = manager.execute(_get_probe_path('hunter_probe.py'), f)
    try:
        data = json.loads(res_ht['stdout'])
        for d in data if isinstance(data, list) else [data]:
            d['file'] = f
            results.append(d)
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context=f'Static Probes (Hunter) -> {os.path.basename(f)}', debug=True)
    return results

def _filter_by_cache(files, cache, io_manager, state, force_no_cache):
    to_scan = []
    for fp in files:
        mtime, _ = io_manager.get_file_metadata(fp)
        cache_key = fp.replace('\\', '/')
        c_entry = cache.get(cache_key)
        if not force_no_cache and c_entry and (c_entry.get('mtime') == mtime):
            if not any((f.get('category') == 'SYSTEM' for f in c_entry.get('findings', []))):
                for f in c_entry.get('findings', []):
                    state.register_finding(f)
                continue
        to_scan.append((fp, cache_key, mtime, 0))
    return to_scan

def _run_clone_detection(files, manager, state):
    from ..check import _get_probe_path
    res = manager.execute(_get_probe_path('clone_probe.py'), payload={'files': files})
    if res['success'] and res['stdout']:
        try:
            clones = json.loads(res['stdout'])
            for c in clones:
                state.register_finding(c)
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context='Clone Detection JSON Parse', debug=True)

def run_check_logic(path: str, state, *_args, **kwargs):
    """
    Bridge de Compatibilidade v93.0 (PASC-Omega).
    Permite que comandos externos (save, merge) usem o motor modular.
    """
    from .check_io import CheckIO
    from .check_filters import apply_filters
    from .check_refactor import analyze_refactor_opportunities
    io = CheckIO(path)
    state = CheckState(root=io.project_root, target_path=io.target_abs, is_full_power=kwargs.get('full_power', False))
    run_audit_engine(state, io, **kwargs)
    apply_filters(state, **kwargs)
    analyze_refactor_opportunities(state)
    return {'summary': state.summary, 'findings': state.findings, 'alb_files': state.alb_files}

def _run_c_cpp_checks(fp):
    """Auditoria de nível industrial para C/C++ usando w64devkit (GCC/G++) (PASC 8.17)."""
    import subprocess
    import re
    import os
    findings = []
    is_cpp = fp.endswith(('.cpp', '.hpp'))
    compiler = 'g++' if is_cpp else 'gcc'
    file_dir = os.path.dirname(os.path.abspath(fp))
    project_root = _find_project_root(file_dir)
    includes = [f'-I{file_dir}']
    if project_root:
        includes.append(f'-I{project_root}')
        for folder in ['include', 'src', 'inc']:
            p = os.path.join(project_root, folder)
            if os.path.isdir(p):
                includes.append(f'-I{p}')
        parent_dir = os.path.dirname(file_dir)
        if parent_dir and parent_dir != project_root:
            includes.append(f'-I{parent_dir}')
            for folder in ['include', 'src', 'inc']:
                p = os.path.join(parent_dir, folder)
                if os.path.isdir(p):
                    includes.append(f'-I{p}')
    cmd = [compiler, '-fsyntax-only', '-Wall', '-Wextra', '-Wpedantic'] + includes + [fp]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        output = result.stderr
        if output:
            gcc_pattern = re.compile('^(.+?):(\\d+):(?:\\d+:)?\\s*(error|warning|note|fatal error):\\s*(.*)$', re.MULTILINE)
            for match in gcc_pattern.finditer(output):
                file_path_gcc = match.group(1)
                line_n = int(match.group(2))
                sev_str = match.group(3).lower()
                msg = match.group(4).strip()
                if 'error' in sev_str:
                    severity = 'CRITICAL'
                    category = 'SYNTAX'
                elif 'warning' in sev_str:
                    severity = 'WARNING'
                    category = 'C-LINT'
                else:
                    severity = 'INFO'
                    category = 'STYLE'
                findings.append({'severity': severity, 'category': category, 'message': f'[{compiler}] {msg}', 'file': fp, 'line': line_n})
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            logic_branches = re.findall('\\b(?:if|for|while|catch|case)\\b', content)
            complexity = len(logic_branches) + 1
            if complexity > 15:
                findings.append({'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f'Arquivo excede limite de complexidade (CC Estimado: {complexity}).', 'file': fp, 'line': 1})
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context='Ponte w64devkit C/C++', silent=True)
        findings.append({'severity': 'ERROR', 'category': 'SYSTEM', 'message': f'Falha ao executar {compiler}. w64devkit está ativo?', 'file': fp, 'line': 0})
    return findings
