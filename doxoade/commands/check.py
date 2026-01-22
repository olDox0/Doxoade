# -*- coding: utf-8 -*-
# doxoade/commands/check.py
import sys
import os
import re
import ast
# [DOX-UNUSED] import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from click import command, argument, option, echo, Path as ClickPath, progressbar, Choice
from colorama import Fore

from ..shared_tools import (
    ExecutionLogger, _get_venv_python_executable, _update_open_incidents,
    _enrich_findings_with_solutions, _find_project_root, _present_results
)

__version__ = "41.8 Alfa (Chief-Gold-Portability)"

CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

# --- FASE 1: INFRA ---

def _get_probe_path(probe_name: str) -> str:
    """Localiza a sonda via Ancoragem Absoluta de Instalação."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Sobe para doxoade/ e entra em probes/
    probe_path = os.path.join(current_dir, "..", "probes", probe_name)
    return os.path.normpath(os.path.abspath(probe_path))

def _load_cache() -> Dict[str, Any]:
    if not CHECK_CACHE_FILE.is_file(): return {}
    from json import load
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f: return load(f)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        _, exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _load_cache\033[0m")
        print(f"\033[31m     ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return {}

def _save_cache(data: Dict[str, Any]) -> None:
    if not data: return
    from json import dump
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f: dump(data, f, indent=2)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        _, exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _save_cache\033[0m")
        print(f"\033[31m     ■ Type: {type(e).__name__} | Value: {e}\033[0m")

# --- FASE 2: SCAN ---

def _run_syntax_check(f: str, manager) -> List[Dict]:
    res = manager.execute(_get_probe_path('syntax_probe.py'), f)
    if not res["success"]:
        m = re.search(r'(?:line |:)(\d+)', res["error"])
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Sintaxe: {res['error']}", 'file': f, 'line': int(m.group(1)) if m else 1}]
    return []

def _run_style_check(f: str) -> List[Dict]:
    if f is None or not os.path.exists(f): return []
    from radon.visitors import ComplexityVisitor
    findings = []
    try:
        with open(f, 'r', encoding='utf-8', errors='ignore') as file:
            tree = ast.parse(file.read())
            v = ComplexityVisitor.from_ast(tree)
            for func in v.functions:
                if func.complexity > 12:
                    findings.append({'severity': 'WARNING', 'category': 'COMPLEXITY', 'message': f"Função '{func.name}' complexa (CC: {func.complexity}).", 'file': f, 'line': func.lineno})
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        _, exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _run_style_check\033[0m")
        print(f"\033[31m     ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    return findings

def _run_static_probes(f: str, manager) -> List[Dict]:
    if not f or not os.path.isfile(f): return []
    from json import loads
    results = []
    res_pf = manager.execute(_get_probe_path('static_probe.py'), f)
    if res_pf["stdout"]:
        for line in res_pf["stdout"].splitlines():
            m = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            if m: results.append({'severity': 'WARNING', 'category': 'STYLE', 'message': m.group(3), 'file': f, 'line': int(m.group(2)), 'suggestion_action': 'FIX_UNUSED_IMPORT' if 'imported but unused' in m.group(3) else None})
    res_ht = manager.execute(_get_probe_path('hunter_probe.py'), f)
    try:
        data = loads(res_ht["stdout"])
        for d in (data if isinstance(data, list) else [data]):
            d['file'] = f
            results.append(d)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        _, exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _run_static_probes\033[0m")
        print(f"\033[31m     ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    return results

# --- FASE 3: FIX ---

def _apply_fixes(findings, root, fix_specify: Optional[str] = None):
    if not findings or not root: return
    from ..fixer import AutoFixer
    files_map = defaultdict(list)
    for f in findings:
        action = f.get('suggestion_action')
        if action and (not fix_specify or action == fix_specify):
            files_map[f['file']].append(f)
    if not files_map: return
    with ExecutionLogger('autofix', root, {'fix_specify': fix_specify}) as f_log:
        fixer = AutoFixer(f_log)
        applied = 0
        for file_path, file_findings in files_map.items():
            file_findings.sort(key=lambda x: x.get('line', 0), reverse=True)
            for f in file_findings:
                var_name = f.get('message', '').split("'")[1] if "'" in f.get('message', '') else None
                if fixer.apply_fix(f['file'], f['line'], f.get('suggestion_action'), {'var_name': var_name}):
                    applied += 1
                    rel = os.path.relpath(f['file'], root)
                    echo(f"{Fore.GREEN}   [ FIX-OK ] {Fore.WHITE}{rel}:{f['line']} -> {f.get('suggestion_action')}")

# --- FASE 4: OPERAÇÃO DO run_check_logic ---

def _setup_environment(path: str) -> tuple:
    """Especialista 1: Configuração de Âncora e Caminhos (Sistema)."""
    doxo_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doxo_anchor = os.path.dirname(doxo_pkg_dir)
    
    # Injeção de Contexto Global
    os.environ["PYTHONPATH"] = doxo_anchor + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONIOENCODING"] = "utf-8"

    target_path = os.path.abspath(path if path else ".")
    project_root = _find_project_root(target_path)
    
    if not project_root or not os.path.isdir(project_root):
        project_root = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
    
    return target_path, os.path.normpath(project_root)

def _initialize_manager(target_path: str, project_root: str):
    """Especialista 2: Gestão de Venv e ProbeManager (Ferramental)."""
    from ..probes.manager import ProbeManager
    py_exe = _get_venv_python_executable(target_path) or sys.executable
    return ProbeManager(py_exe, project_root)

def _execute_scan_cycle(manager, target_path, project_root, **kwargs) -> tuple:
    """Especialista 3: Execução do Pipeline de Sondas (Processamento)."""
    files = _resolve_file_list(target_path, project_root, kwargs.get('target_files'))
    if not files: return [], {}

    cache = {} if kwargs.get('no_cache') else _load_cache()
    raw_findings = []
    
    to_scan = _filter_cache(files, cache, kwargs.get('no_cache'), raw_findings, project_root)
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for item in bar:
                raw_findings.extend(_process_single_file_task(item, manager, kwargs.get('continue_on_error'), cache))
    
    return raw_findings, cache

def _handle_remediation(raw_findings, project_root, **kwargs):
    """Especialista 4: Inteligência e Reparo (Gênese/Fixer)."""
    _enrich_findings_with_solutions(raw_findings, project_root)
    
    fix_spec = kwargs.get('fix_specify')
    fix_active = kwargs.get('fix') or fix_spec is not None
    
    if fix_active:
        _apply_fixes(raw_findings, project_root, fix_spec)
        # Filtro pós-fix: Remove o que foi consertado da exibição
        raw_findings = [f for f in raw_findings if not f.get('suggestion_action') or (fix_spec and f.get('suggestion_action') != fix_spec)]
    
    return raw_findings, fix_active

# --- FASE 5: ORCHESTRATION ---

def run_check_logic(path: str, **kwargs):
    """
    Coordena os especialistas de Auditoria. 
    Complexidade Ciclomática: 2 (Nexus Level).
    """
    # 1. Setup e Manager
    target_path, project_root = _setup_environment(path)
    manager = _initialize_manager(target_path, project_root)

    # 2. Scan
    raw_findings, cache = _execute_scan_cycle(manager, target_path, project_root, **kwargs)
    if not raw_findings and not cache:
        return {'summary': {'errors': 0, 'warnings': 0}, 'findings': []}

    # 3. Inteligência e Fix
    processed_findings, fix_was_active = _handle_remediation(raw_findings, project_root, **kwargs)

    # 4. Report Final
    return _finalize_report(processed_findings, project_root, cache, fix_active=fix_was_active, **kwargs)

def _finalize_report(raw_findings, project_root, cache, **kwargs):
    # RESOLVIDO: Busca segura no kwargs para evitar NameError
    fix_active = kwargs.get('fix', False) or kwargs.get('fix_specify') is not None
    only_cat = kwargs.get('only_category')
    arch_mode = kwargs.get('archives_mode', False)
    no_cache = kwargs.get('no_cache', False)

    with ExecutionLogger('check', project_root, {'fix': fix_active, 'only': only_cat, 'archives': arch_mode}) as logger:
        from .check_filters import filter_and_inject_findings
        from .check_utils import _finalize_log
        
        processed = filter_and_inject_findings(raw_findings, project_root)
        if only_cat:
            processed = [f for f in processed if f.get('category', '').upper() == only_cat.upper()]
        
        _finalize_log(processed, logger, project_root, kwargs.get('exclude_categories'))
        if not no_cache: _save_cache(cache)
        return logger.results

def _resolve_file_list(abs_path, root, target_files):
    if target_files: return [os.path.abspath(f) for f in target_files]
    
    # Se for um arquivo específico, retorna apenas ele
    if os.path.isfile(abs_path): return [abs_path]
    
    from ..dnm import DNM
    # DNM scan agora é ancorado no path alvo para garantir descoberta em outros projetos
    found = DNM(root).scan(extensions=['.py'])
    
    # Se o DNM falhou ou estamos em uma subpasta, filtramos pelo caminho absoluto
    return [f for f in found if os.path.abspath(f).startswith(abs_path)]

def _filter_cache(files, cache, no_cache, raw_findings, root):
    to_scan = []
    for fp in files:
        # Se o arquivo está fora da raiz (projeto externo sem git), relpath pode falhar
        try:
            rel = os.path.relpath(fp, root).replace('\\', '/')
            st = os.stat(fp)
            c = cache.get(rel, {})
            if not no_cache and c.get('mtime') == st.st_mtime:
                for f in c.get('findings', []):
                    f['file'] = fp
                    raw_findings.append(f)
                continue
            to_scan.append((fp, rel, st.st_mtime, st.st_size))
        except (OSError, ValueError):
            # Fallback para arquivos fora da raiz detectada
            to_scan.append((fp, os.path.basename(fp), 0, 0))
    return to_scan

def _process_single_file_task(item, manager, cont_error, cache):
    fp, rel, mtime, size = item
    fnd = _run_syntax_check(fp, manager)
    if not fnd or cont_error:
        fnd.extend(_run_static_probes(fp, manager))
        fnd.extend(_run_style_check(fp))
    # Só salva no cache se tivermos metadados válidos
    if mtime > 0:
        cache[rel] = {'mtime': mtime, 'size': size, 'findings': fnd}
    return fnd

# --- CLICK COMMAND MANTIDO ---
@command('check')
@argument('path', type=ClickPath(exists=True), default='.')
@option('--fix', is_flag=True, help="Corrige problemas.")
@option('--fix-specify', '-fs', type=str, help="Reparo específico.")
@option('--only', '-o', type=str, help="Filtra categoria.")
@option('--archives', '-a', is_flag=True, help="Modo Dossiê.")
@option('--fast', is_flag=True, help="Pula pesados.")
@option('--no-cache', is_flag=True, help="Força reanálise.")
@option('--clones', is_flag=True, help="Análise DRY.")
@option('--continue-on-error', '-C', is_flag=True, help="Ignora sintaxe.")
@option('--exclude', '-x', multiple=True, help="Ignora categorias.")
@option('--format', 'out_fmt', type=Choice(['text', 'json']), default='text')
def check(path: str, **kwargs):
    """🔍 Auditoria de Qualidade e Segurança (Chief-Gold)."""
    if not path: raise ValueError("Caminho obrigatório.")
    if kwargs.get('out_fmt', 'text') == 'text': echo(Fore.YELLOW + "[CHECK] Executando auditoria...")

    results = run_check_logic(
        path, fix=kwargs.get('fix'), fast=kwargs.get('fast'), no_cache=kwargs.get('no_cache'), 
        clones=kwargs.get('clones'), continue_on_error=kwargs.get('continue_on_error'), 
        exclude_categories=kwargs.get('exclude'), fix_specify=kwargs.get('fix_specify'),
        only_category=kwargs.get('only'), archives_mode=kwargs.get('archives')
    )
    
    _update_open_incidents(results, os.path.abspath(path))
    
    if kwargs.get('out_fmt') == 'json':
        from json import dumps
        echo(dumps(results, indent=2, ensure_ascii=False))
    elif kwargs.get('archives'):
        from .check_utils import _render_issue_summary, _render_archived_view
        _render_archived_view(results)
        _render_issue_summary(results.get('findings', []))
    else:
        from .check_utils import _render_issue_summary
        _present_results('text', results)
        _render_issue_summary(results.get('findings', []))
    if results.get('summary', {}).get('critical', 0) > 0: sys.exit(1)