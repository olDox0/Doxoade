# -*- coding: utf-8 -*-
"""
Security Suite - Chief Gold Edition.
SAST (Bandit) & SCA (Safety) integration with double-filtering.
Compliance: MPoT-4, MPoT-5, PASC-6.
"""

import sys
import os
import shutil
import logging
from click import command, argument, option, echo, Choice, pass_context
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_venv_python_executable, _get_project_config

__all__ = ['security']

# Mapeamento para comparação de severidade
SEVERITY_MAP = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

# ============================================================================
# FASE 1: LOCALIZAÇÃO E FILTRAGEM (MPoT-17)
# ============================================================================

def _get_tool_path(tool_name: str) -> str:
    """Localiza o executável da ferramenta via heurística multinível."""
    if not tool_name:
        raise ValueError("Contrato Violado: 'tool_name' é obrigatório.")
    
    exe = tool_name + ('.exe' if os.name == 'nt' else '')
    
    # 1. Venv do Alvo
    target_py = _get_venv_python_executable()
    if target_py:
        target_dir = os.path.dirname(target_py)
        for sub in ['', 'Scripts', 'bin']:
            p = os.path.join(target_dir, sub, exe)
            if os.path.exists(p): return p

    # 2. Ambiente Atual
    curr_py_dir = os.path.dirname(sys.executable)
    for sub in ['', 'Scripts', 'bin']:
        p = os.path.join(curr_py_dir, sub, exe)
        if os.path.exists(p): return p

    # 3. Fallback PATH
    return shutil.which(tool_name)

def _is_file_ignored(filepath: str, ignores: list) -> bool:
    """Verifica se o arquivo pertence a diretórios ignorados (Aegis)."""
    norm_path = os.path.normpath(filepath)
    parts = norm_path.split(os.sep)
    clean_ignores = {os.path.normpath(i).strip(os.sep) for i in ignores}
    return any(part in clean_ignores for part in parts)

# ============================================================================
# FASE 2: EXECUTORES ESPECIALISTAS (SAST/SCA)
# ============================================================================

def _run_bandit(target: str, config_ignore: list) -> list:
    """Executa Bandit (SAST) com parsing JSON e filtragem manual."""
    if not target:
        raise ValueError("Contrato Violado: 'target' é obrigatório para Bandit.")
    
    tool = _get_tool_path('bandit')
    if not tool: return []
    
    from json import loads
    from subprocess import run # nosec - PASC-6.1
    
    sys_excludes = ["venv", ".git", "__pycache__", "build", "dist", "site-packages", "tests"]
    # Garante que operamos com listas limpas
    clean_custom = [str(i).strip('/\\') for i in (config_ignore or [])]
    final_excludes = list(set(sys_excludes + clean_custom))
    
    echo(Fore.YELLOW + f"   > Executando SAST (Bandit)... (Ignorando: {len(final_excludes)} dirs)")
    
    cmd = [tool, '-r', target, '-f', 'json', '-q', '-x', ",".join(final_excludes)]
    try:
        res = run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, shell=False) # nosec
        data = loads(res.stdout)
        findings = []
        for item in data.get('results', []):
            fname = item.get('filename', '')
            if _is_file_ignored(fname, final_excludes): continue
            findings.append({
                'tool': 'BANDIT', 'severity': item['issue_severity'],
                'message': item['issue_text'], 'file': fname,
                'line': item['line_number'], 'code': item['code'].strip()
            })
        return findings
    except Exception as e:
        logging.debug(f"Bandit execution failed: {e}")
        return []

def _run_safety(logger: ExecutionLogger) -> list:
    """
    Executa Safety (SCA) para auditoria de dependências (PASC-6.2).
    """
    # MPoT-5: Contrato de Integridade
    if logger is None:
        raise ValueError("Contrato Violado: 'logger' é obrigatório para telemetria Safety.")

    tool = _get_tool_path('safety')
    if not tool: return []
    
    from json import loads
    from subprocess import run # nosec
    echo(Fore.YELLOW + "   > Executando SCA (Safety)...")
    
    try:
        res = run([tool, 'check', '--json'], capture_output=True, text=True, encoding='utf-8', timeout=60, shell=False) # nosec
        data = loads(res.stdout)
        findings = []
        
        # Normalização de saída (v2+ retorna dict, v1 retorna list)
        vulns = data.get('vulnerabilities', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        for item in vulns:
            pkg = item.get('package_name', item.get('name', 'unknown'))
            ver = item.get('installed_version', item.get('version', '?'))
            desc = item.get('advisory', 'No description')
            
            findings.append({
                'tool': 'SAFETY', 'severity': 'HIGH', 'file': 'requirements.txt', 'line': 0,
                'message': f"Vulnerabilidade em {pkg} ({ver}): {desc}"
            })
        return findings
    except Exception as e:
        logger.add_finding('ERROR', f"Safety failed: {e}", category='SECURITY')
        return []

# ============================================================================
# FASE 3: RENDERIZADORES (UI/UX Chief-Gold)
# ============================================================================

def _display_findings(findings: list, level: str, logger: ExecutionLogger):
    """Renderiza os achados respeitando o filtro de severidade (MPoT-4)."""
    # MPoT-5: Contrato de Robustez
    if findings is None:
        raise ValueError("Contrato Violado: 'findings' não pode ser None.")
        
    target_val = SEVERITY_MAP.get(level, 1)
    visible = []
    hidden_count = 0

    for f in findings:
        f_val = SEVERITY_MAP.get(f['severity'].upper(), 1)
        if f_val >= target_val: visible.append(f)
        else: hidden_count += 1

    if not visible:
        msg = f"\n[OK] Nenhum problema nível {level}+ encontrado."
        echo(Fore.GREEN + msg + (f" ({hidden_count} menores ocultos)" if hidden_count > 0 else ""))
        return

    echo(Fore.RED + Style.BRIGHT + f"\n[ALERTA] {len(visible)} problemas detectados (Filtro: {level}+)!")
    
    for f in visible:
        sev = f['severity'].upper()
        color = Fore.RED if sev in ['HIGH', 'CRITICAL'] else (Fore.YELLOW if sev == 'MEDIUM' else Fore.WHITE)
        echo(f"\n{color}[{f['tool']}][{sev}] {f['message']}")
        echo(Fore.WHITE + f"   > Em: {f['file']}:{f['line']}")
        if f.get('code'): echo(Fore.CYAN + f"   > Código: {f['code']}")
        
        # Loga no banco (Persistência Assíncrona via Core)
        log_sev = 'CRITICAL' if sev in ['HIGH', 'CRITICAL'] else 'WARNING'
        logger.add_finding(
            severity=log_sev,
            category='SECURITY', message=f"[{f['tool']}] {f['message']}",
            file=f['file'], line=f['line']
        )

# ============================================================================
# FASE 4: ORQUESTRADOR PRINCIPAL
# ============================================================================

@command('security')
@argument('target', default='.')
@option('--sast', is_flag=True, help="Apenas Bandit.")
@option('--sca', is_flag=True, help="Apenas Safety.")
@option('--level', '-l', type=Choice(['LOW', 'MEDIUM', 'HIGH']), default='LOW', help="Severidade mínima.")
@pass_context
def security(ctx, target, sast, sca, level):
    """Realiza auditoria de segurança (SAST + SCA) (MPoT-5)."""
    # MPoT-5: Contrato de Integridade
    if not target or not os.path.exists(target):
        raise ValueError(f"Security Error: Alvo '{target}' não existe.")

    with ExecutionLogger('security', target, ctx.params) as logger:
        echo(Fore.CYAN + f"--- [SECURITY] Auditoria em '{target}' ---")
        echo(Fore.WHITE + Style.DIM + f"   > Nível de filtro: {level}+")
        
        config = _get_project_config(logger, start_path=target)
        run_all = not (sast or sca)
        findings = []

        if (run_all or sast): 
            findings.extend(_run_bandit(target, config.get('ignore', [])))
            
        if (run_all or sca): 
            findings.extend(_run_safety(logger))

        _display_findings(findings, level, logger)
        
        if any(f['severity'].upper() in ['HIGH', 'CRITICAL'] for f in findings):
            echo(Fore.RED + "\nRecomendação: Revise estas vulnerabilidades imediatamente.")