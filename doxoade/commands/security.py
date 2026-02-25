# -*- coding: utf-8 -*-
# doxoade/commands/security.py:
"""
Security Suite - Chief Gold Edition.
Performance: PASC-6.4 Consolidated Batching.
"""
import os
import sys
import re
# [FIX STYLE] Removidos loads e JSONDecodeError daqui para usar imports locais
from subprocess import run, PIPE
from click import command, argument, option, pass_context, Choice
from .security_utils import get_tool_path, get_essential_ignores, SEVERITY_MAP, batch_list
from .security_io import print_header, render_findings, get_progress_bar
from ..shared_tools import ExecutionLogger, _get_project_config
def _execute_security_pipeline(target, ignore_set, logger):
    from ..dnm import DNM
    dnm = DNM(target)
    py_files = dnm.scan(extensions=['py'])
    findings = []
    
    if py_files:
        batches = list(batch_list(py_files, 40))
        with get_progress_bar(batches, label="Análise SAST") as bar:
            for item_batch in bar:
                result = _run_bandit_engine(item_batch, ignore_set)
                if result: findings.extend(result)
    # 3. Análise SCA (Safety) - FIX: Indentação e Loop
    with get_progress_bar([["requirements.txt"]], label="Análise SCA ") as bar:
        for _ in bar:
            sca_res = _run_safety_engine(target, logger)
            if sca_res: findings.extend(sca_res)
            
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
    import json # FIX: Usando local para evitar 'redefinition'
    tool = get_tool_path('bandit')
    if not tool or not file_list: return []
    cmd = [tool, '-f', 'json'] + file_list
    try:
        res = run(cmd, stdout=PIPE, stderr=PIPE, text=True, encoding='utf-8')
        if not res.stdout: return []
        data = json.loads(res.stdout)
        return [{
            'tool': 'BANDIT', 'severity': i['issue_severity'].upper(),
            'message': i['issue_text'], 'file': i['filename'],
            'line': i['line_number'], 'code': i['code'].strip()
        } for i in data.get('results', [])]
    except Exception: return []
def _run_safety_engine(target, logger):
    """Orquestrador SCA resiliente (CC: 3)."""
    tool = get_tool_path('safety')
    req_file = os.path.join(target, 'requirements.txt')
    if not tool or not os.path.exists(req_file): return []
    
    try:
        # shell=False + PIPE (Aegis Shield)
        res = run([tool, 'check', '-r', req_file, '--json'], stdout=PIPE, stderr=PIPE, text=True, timeout=60)
        return _parse_safety_output(res.stdout) if res.stdout else []
    except Exception as e:
        print(f"\033[31m   [!] Erro crítico no motor SCA: {e}\033[0m")
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return []
def _parse_safety_output(raw_stdout: str) -> list:
    """Decodificador Cirúrgico (MPoT-7)."""
    import json
    raw_stdout = raw_stdout.strip()
    if not raw_stdout: return []
    # 1. Localiza o início real do JSON (pode haver warnings de texto antes)
    match = re.search(r'[\[\{]', raw_stdout)
    if not match: return []
    
    content = raw_stdout[match.start():]
    
    try:
        # raw_decode lê exatamente um objeto/lista e para, ignorando "Extra Data"
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(content)
        
        # 2. Normalização de formato (Safety v2 vs v3)
        vulns = data.get('vulnerabilities', []) if isinstance(data, dict) else data
        if not isinstance(vulns, list): vulns = []
        
        return [{
            'tool': 'SAFETY', 'severity': 'HIGH',
            'message': f"Vulnerabilidade: {v.get('package_name')} -> {v.get('advisory', 'risco detectado')}",
            'file': 'requirements.txt', 'line': 0
        } for v in vulns]
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return []
def _print_security_forensic(scope: str, e: Exception):
    """Log forense independente para evitar dependências circulares."""
    print(f"\033[1;34m\n[ FORENSIC:SECURITY:{scope} ]\033[0m \033[31m Erro: {e}\033[0m")