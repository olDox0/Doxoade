# -*- coding: utf-8 -*-
"""
Módulo Auditor Mestre (Check) - v41.0 Gold Standard.
Refatoração Final: Zero-Warnings, MPoT-5 e PASC-6.1 (Lazy Core).
"""

import sys
import os
import re
import ast
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# ClickPath e Choice importados para uso explícito nos decorators
from click import command, argument, option, echo, Path as ClickPath, progressbar, Choice
from colorama import Fore

# PASC-6.1: Verbosidade Seletiva (Apenas o vital no escopo global)
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _get_code_snippet, 
    _present_results, 
    _update_open_incidents,
    _enrich_findings_with_solutions,
    _find_project_root
)
#from ..dnm import DNM 
#from .check_filters import filter_and_inject_findings
#from ..fixer import AutoFixer
#from ..probes.manager import ProbeManager

__version__ = "41.0 Alfa (Chief-Gold-Consolidated)"
__all__ = ['check']

CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

# ============================================================================
# FASE 1: UTILITÁRIOS (API Moderna)
# ============================================================================

def _get_probe_path(probe_name: str) -> str:
    """Localiza o script da sonda via importlib.resources (MPoT-18)."""
    if not probe_name: return ""
    try:
        from importlib import resources
        return str(resources.files('doxoade.probes').joinpath(probe_name))
    except (ImportError, AttributeError):
        return os.path.join(os.path.dirname(__file__), "..", "probes", probe_name)

def _load_cache() -> Dict[str, Any]:
    """Carrega o cache de análise do disco (MPoT-7)."""
    if not CHECK_CACHE_FILE.is_file(): return {}
    from json import load
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f: return load(f)
    except Exception: return {}

def _save_cache(data: Dict[str, Any]) -> None:
    """Persiste o cache no disco (PASC-6.3)."""
    if not data: return
    from json import dump
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f: dump(data, f, indent=2)
    except Exception as e:
        logging.debug(f"Erro ao salvar cache: {e}")

# ============================================================================
# FASE 2: ANALISADORES ESPECIALISTAS (Expert-Split)
# ============================================================================

def _run_syntax_check(f: str, manager) -> List[Dict]:
    """Sonda de integridade sintática (Fast-Fail)."""
    res = manager.execute(_get_probe_path('syntax_probe.py'), f)
    if not res["success"]:
        m = re.search(r'(?:line |:)(\d+)', res["error"])
        line = int(m.group(1)) if m else 1
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Sintaxe Inválida: {res['error']}", 'file': f, 'line': line}]
    return []

def _run_style_check(f: str) -> List[Dict]:
    """Validação de Complexidade e MPoT-Style."""
    # MPoT-5: Contrato de Integridade
    if not f or not os.path.exists(f): return []
    if f is None:
        raise ValueError("_run_style_check: str 'f' não pode ser None.")
    
    from radon.visitors import ComplexityVisitor
    findings = []
    try:
        with open(f, 'r', encoding='utf-8', errors='ignore') as file:
            tree = ast.parse(file.read())
            v = ComplexityVisitor.from_ast(tree)
            for func in v.functions:
                if func.complexity > 12:
                    findings.append({
                        'severity': 'WARNING', 'category': 'COMPLEXITY',
                        'message': f"Função '{func.name}' complexa (CC: {func.complexity}).",
                        'file': f, 'line': func.lineno
                    })
    except Exception as e:
        logging.debug(f"Falha no Style Check: {e}")
    return findings

# ============================================================================
# FASE 3: ORQUESTRADOR (CC < 10)
# ============================================================================

def run_check_logic(path: str, fix: bool, fast: bool, no_cache: bool, 
                    clones: bool, continue_on_error: bool, exclude_categories: Optional[List[str]] = None,
                    target_files: Optional[List[str]] = None):
    """
    Orquestrador Master de Auditoria (MPoT-4).
    Reduzido para CC < 10 através de deleção de responsabilidade.
    """
    if path is None:
        raise ValueError("run_check_logic: str 'path' não pode ser None.")
        
    from ..probes.manager import ProbeManager
    abs_path = os.path.abspath(path)
    project_root = _find_project_root(abs_path)
    
    files = _resolve_file_list(abs_path, project_root, target_files)
    if not files: return {'summary': {'errors': 0, 'warnings': 0}, 'findings': []}

    cache = {} if no_cache else _load_cache()
    py_exe = _get_venv_python_executable() or sys.executable
    manager = ProbeManager(py_exe, project_root)
    raw_findings = []
    
    # 1. Auditoria Individual (Com Cache)
    to_scan = _filter_cache(files, cache, no_cache, raw_findings, project_root)
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for item in bar:
                raw_findings.extend(_process_single_file_task(item, manager, continue_on_error, cache))

    # 2. Auditoria Estrutural
    if not fast:
        raw_findings.extend(_run_structural_analysis(manager, files, project_root))

    _enrich_findings_with_solutions(raw_findings, project_root)
    if fix: _apply_fixes(raw_findings, project_root)

    # 3. Finalização
    with ExecutionLogger('check', project_root, {'fix': fix}) as logger:
        from .check_filters import filter_and_inject_findings
        processed = filter_and_inject_findings(raw_findings, project_root)
        _finalize_log(processed, logger, project_root, exclude_categories)
        if not no_cache: _save_cache(cache)
        return logger.results

def _resolve_file_list(abs_path: str, root: str, target_files: Optional[list]) -> List[str]:
    """Resolve alvos respeitando DNM e inputs (MPoT-17)."""
    if target_files: return [os.path.abspath(f) for f in target_files]
    if os.path.isfile(abs_path): return [abs_path]
    from ..dnm import DNM
    return [f for f in DNM(root).scan(extensions=['.py']) if os.path.abspath(f).startswith(abs_path)]

def _filter_cache(files, cache, no_cache, raw_findings, root) -> list:
    """MPoT-7: Filtro de cache resiliente."""
    to_scan = []
    for fp in files:
        rel = os.path.relpath(fp, root).replace('\\', '/')
        try:
            st = os.stat(fp)
            c = cache.get(rel, {})
            if not no_cache and c.get('mtime') == st.st_mtime and c.get('size') == st.st_size:
                for f in c.get('findings', []):
                    f['file'] = fp
                    raw_findings.append(f)
                continue
            to_scan.append((fp, rel, st.st_mtime, st.st_size))
        except OSError: continue
    return to_scan

def _process_single_file_task(item: tuple, manager, continue_on_error: bool,
                              cache: dict) -> list:
    """Pipeline de um arquivo único (MPoT-5)."""
    fp, rel, mtime, size = item
    if item is None:
        raise ValueError("_process_single_file_task: tuple 'item' não pode ser None.")

    fnd = _run_syntax_check(fp, manager)
    if not fnd or continue_on_error:
        fnd.extend(_run_static_probes(fp, manager))
        fnd.extend(_run_style_check(fp))
    cache[rel] = {'mtime': mtime, 'size': size, 'findings': fnd}
    return fnd

def _run_static_probes(f: str, manager) -> List[Dict]:
    """Executa Pyflakes e Hunter (MPoT-17)."""
    from json import loads
    if f is None:
        raise ValueError("_run_static_probes: str 'f' não pode ser None.")

    results = []
    # Pyflakes
    res_pf = manager.execute(_get_probe_path('static_probe.py'), f)
    if res_pf["stdout"]:
        for line in res_pf["stdout"].splitlines():
            m = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            if m: results.append({'severity': 'WARNING', 'category': 'STYLE', 'message': m.group(3), 'file': f, 'line': int(m.group(2))})
    # Hunter
    res_ht = manager.execute(_get_probe_path('hunter_probe.py'), f)
    try:
        data = loads(res_ht["stdout"])
        for d in (data if isinstance(data, list) else [data]):
            d['file'] = f
            results.append(d)
    except Exception as e:
        logging.error(f" _run_static_probes: {e}")
    return results

def _run_structural_analysis(manager, files: list, root: str) -> list:
    """Executa análises globais (Clones, XREF)."""
    from json import loads
    found = []
    if files is None:
        raise ValueError("_run_structural_analysis: list 'files' não pode ser None.")

    payload = {"files": [os.path.abspath(f) for f in files], "project_root": root}
    for probe in ['clone_probe.py', 'orphan_probe.py', 'xref_probe.py']:
        res = manager.execute(_get_probe_path(probe), root if 'xref' in probe else None, payload=payload)
        try:
            if res["stdout"].strip():
                data = loads(res["stdout"])
                for d in data:
                    if 'file' in d: d['file'] = os.path.normpath(d['file'])
                    found.append(d)
        except Exception as e:
            logging.error(f" _run_structural_analysis: {e}")
    return found

def _finalize_log(findings, logger, root, excludes):
    """Envia os achados para o logger do core."""
    exclude_set = set([c.upper() for c in (excludes or [])])
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat in exclude_set: continue
        abs_f = os.path.abspath(f['file'])
        logger.add_finding(
            severity=f['severity'], message=f['message'], category=cat,
            file=os.path.relpath(abs_f, root), line=f.get('line', 0),
            snippet=_get_code_snippet(abs_f, f.get('line')),
            finding_hash=f.get('hash'),
            suggestion_content=f.get('suggestion_content'),
            suggestion_action=f.get('suggestion_action')
        )

def _apply_fixes(findings, root):
    """Interface para aplicação de AutoFixer (PASC-1)."""
    if not findings: return
    from ..fixer import AutoFixer
    with ExecutionLogger('autofix', root, {}) as f_log:
        _ = AutoFixer(f_log) # Reservado para expansão futura
        pass

# ============================================================================
# FASE 4: CLICK COMMAND
# ============================================================================

@command('check')
@argument('path', type=ClickPath(exists=True), default='.')
@option('--fix', is_flag=True, help="Corrige problemas.")
@option('--fast', is_flag=True, help="Pula análises pesadas.")
@option('--no-cache', is_flag=True, help="Força reanálise.")
@option('--clones', is_flag=True, help="Análise DRY.")
@option('--continue-on-error', '-C', is_flag=True, help="Ignora erros de sintaxe.")
@option('--exclude', '-x', multiple=True, help="Categorias ignoradas.")
@option('--format', 'out_fmt', type=Choice(['text', 'json']), default='text')
def check(path: str, **kwargs):
    """Análise completa de qualidade e segurança (MPoT-5)."""
    if not path: raise ValueError("Caminho obrigatório.")
    if kwargs.get('out_fmt') == 'text':
        echo(Fore.YELLOW + "[CHECK] Executando auditoria...")

    results = run_check_logic(
        path, kwargs.get('fix'), kwargs.get('fast'), kwargs.get('no_cache'), 
        kwargs.get('clones'), kwargs.get('continue_on_error'), kwargs.get('exclude')
    )
    
    _update_open_incidents(results, os.path.abspath(path))
    
    if kwargs.get('out_fmt') == 'json':
        from json import dumps
        echo(dumps(results, indent=2, ensure_ascii=False))
    else:
        _present_results('text', results)
        
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)

if __name__ == "__main__":
    # PASC-8: Entrypoint isolado para diagnósticos diretos
    try:
        if len(sys.argv) > 1: pass
    except Exception as e:
        print(f"Erro fatal no entrypoint: {e}", file=sys.stderr)