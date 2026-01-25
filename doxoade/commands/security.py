# -*- coding: utf-8 -*-
"""
Security Suite - Chief Gold Edition.
Performance: PASC-6.4 Consolidated Batching.
"""
import os
from click import command, argument, option, pass_context, Choice
from .security_utils import get_tool_path, is_path_ignored, get_essential_ignores, SEVERITY_MAP, batch_list
from .security_io import print_header, render_findings, get_progress_bar
from ..shared_tools import ExecutionLogger, _get_project_config

def _execute_security_pipeline(target, ignore_set, logger):
    """Pipeline de alta performance com DNM e Batching (MPoT-2)."""
    from ..dnm import DNM
    
    # DNM Scan é pesado, chamamos apenas uma vez (MPoT-17)
    dnm = DNM(target)
    py_files = dnm.scan(extensions=['py'])
    
    findings = []
    
    if py_files:
        # PASC-6.4: Batching de 40 arquivos (Equilíbrio entre UI e Performance)
        batches = list(batch_list(py_files, 40))
        
        with get_progress_bar(batches, label="Análise SAST") as bar:
            for batch in bar:
                result = _run_bandit_engine(batch, ignore_set)
                if result:
                    findings.extend(result)

    # Análise SCA (Safety)
    with get_progress_bar([["requirements.txt"]], label="Análise SCA ") as bar:
        for _ in bar:
            findings.extend(_run_safety_engine(target, logger))
            
    return findings

def _run_security_logic(ctx_params, target, level, logger):
    target_abs = os.path.abspath(target)
    print_header(target_abs, level)
    
    config = _get_project_config(logger, start_path=target_abs)
    # Converte para set para busca O(1) no Utils
    ignore_set = set(config.get('ignore') or []) | get_essential_ignores()
    
    findings = _execute_security_pipeline(target_abs, ignore_set, logger)
    
    min_level_int = SEVERITY_MAP.get(level.upper(), 1)
    render_findings(findings, min_level_int, SEVERITY_MAP)

@command('security')
@argument('target', default='.')
@option('--level', '-l', type=Choice(['LOW', 'MEDIUM', 'HIGH']), default='LOW')
@pass_context
def security(ctx, target, level):
    """Auditoria de Segurança (MPoT-5)."""
    with ExecutionLogger('security', target, ctx.params) as logger:
        _run_security_logic(ctx.params, target, level, logger)

def _run_bandit_engine(file_list, ignore_set):
    """Motor SAST focado em processamento de lista."""
    from json import loads
    from subprocess import run
    
    tool = get_tool_path('bandit')
    if not tool or not file_list: return []

    # Comando otimizado: passa a lista de arquivos direta para evitar re-scan do Bandit
    cmd = [tool, '-f', 'json', '-q'] + file_list
    
    try:
        res = run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)
        if not res.stdout: return []
        
        data = loads(res.stdout)
        # Filtro Aegis no retorno para garantir integridade
        return [
            {
                'tool': 'BANDIT', 'severity': i['issue_severity'].upper(),
                'message': i['issue_text'], 'file': i['filename'],
                'line': i['line_number'], 'code': i['code'].strip()
            }
            for i in data.get('results', [])
            if not is_path_ignored(i['filename'], ignore_set)
        ]
    except Exception:
        return []

def _run_safety_engine(target, logger):
    from subprocess import run
    from json import loads
    tool = get_tool_path('safety')
    req_file = os.path.join(target, 'requirements.txt')
    if not tool or not os.path.exists(req_file): return []
    try:
        res = run([tool, 'check', '-r', req_file, '--json'], capture_output=True, text=True, timeout=60)
        if not res.stdout: return []
        data = loads(res.stdout)
        vulns = data.get('vulnerabilities', []) if isinstance(data, dict) else data
        return [{
            'tool': 'SAFETY', 'severity': 'HIGH',
            'message': f"Vulnerabilidade: {v.get('package_name')} -> {v.get('advisory')}",
            'file': 'requirements.txt', 'line': 0
        } for v in vulns]
    except Exception: return []