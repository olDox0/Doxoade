# doxoade/commands/security.py
import sys
import subprocess
import shutil
import os
import json
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_venv_python_executable

def _get_tool_path(tool_name):
    """
    Localiza o executável da ferramenta de segurança.
    
    Estratégia de Busca:
    1. Venv do Projeto Alvo (Prioridade: Override do usuário).
    2. Ambiente do Interpretador Atual (Onde o doxoade está rodando).
    3. [NOVO] Venv da Fonte do Doxoade (Baseado na localização do arquivo).
    4. PATH Global.
    """
    tool_exe = tool_name + ('.exe' if os.name == 'nt' else '')
    
    # 1. Busca no Venv do Projeto Alvo
    target_python = _get_venv_python_executable()
    if target_python:
        target_venv_dir = os.path.dirname(target_python)
        # Verifica raiz, Scripts e bin
        for sub in ['', 'Scripts', 'bin']:
            path = os.path.join(target_venv_dir, sub, tool_exe)
            if os.path.exists(path): return path

    # 2. Busca no Ambiente do Interpretador Atual (Sys Executable)
    current_python_dir = os.path.dirname(sys.executable)
    # Tenta Scripts/ (Win) e bin/ (Linux) e raiz
    possible_dirs = [
        current_python_dir,
        os.path.join(current_python_dir, 'Scripts'),
        os.path.join(current_python_dir, 'bin')
    ]
    for d in possible_dirs:
        path = os.path.join(d, tool_exe)
        if os.path.exists(path): return path

    # 3. [NOVO] Busca Baseada na Localização do Código Fonte (Editable Mode Magic)
    # Se estamos rodando de um 'pip install -e .', __file__ aponta para o source.
    # Estrutura esperada: .../Projeto OADE/doxoade/doxoade/commands/security.py
    # Venv esperado:      .../Projeto OADE/doxoade/venv
    
    try:
        # Sobe 3 níveis: commands -> doxoade (pkg) -> root
        current_file = os.path.abspath(__file__)
        pkg_dir = os.path.dirname(os.path.dirname(current_file)) # .../doxoade/doxoade
        root_dir = os.path.dirname(pkg_dir) # .../doxoade
        
        source_venv_dirs = [
            os.path.join(root_dir, 'venv', 'Scripts'), # Windows Source Venv
            os.path.join(root_dir, 'venv', 'bin')      # Linux Source Venv
        ]
        
        for d in source_venv_dirs:
            path = os.path.join(d, tool_exe)
            if os.path.exists(path): 
                # click.echo(f"[DEBUG] Ferramenta encontrada na fonte: {path}")
                return path
    except Exception: pass

    # 4. Fallback para PATH Global
    return shutil.which(tool_name)

def _check_tool(tool_name):
    return _get_tool_path(tool_name) is not None

def _run_bandit(target, logger):
    tool = _get_tool_path('bandit')
    if not tool: 
        click.echo(Fore.RED + "   [ERRO] Executável do Bandit não encontrado.")
        return []
    
    click.echo(Fore.YELLOW + "   > Executando SAST (Bandit)...")
    excludes = "venv,.git,__pycache__,build,dist,.doxoade_cache,site-packages"
    cmd = [tool, '-r', target, '-f', 'json', '-q', '-x', excludes]
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120
        )
        try:
            data = json.loads(result.stdout)
            findings = []
            for item in data.get('results', []):
                findings.append({
                    'tool': 'BANDIT',
                    'severity': item['issue_severity'],
                    'confidence': item['issue_confidence'],
                    'message': item['issue_text'],
                    'file': item['filename'],
                    'line': item['line_number'],
                    'code': item['code'].strip()
                })
            return findings
        except json.JSONDecodeError: return []
    except Exception as e:
        logger.add_finding('ERROR', f"Erro ao executar Bandit: {e}")
        return []

def _run_safety(logger):
    tool = _get_tool_path('safety')
    if not tool: 
        click.echo(Fore.RED + "   [ERRO] Executável do Safety não encontrado.")
        return []
    
    click.echo(Fore.YELLOW + "   > Executando SCA (Safety)...")
    cmd = [tool, 'check', '--json']

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
        )
        try:
            data = json.loads(result.stdout)
            findings = []
            if isinstance(data, dict) and 'vulnerabilities' in data: vulns = data['vulnerabilities']
            else: vulns = data 
            
            for item in vulns:
                pkg = item.get('package_name', item.get('name', 'unknown'))
                ver = item.get('installed_version', item.get('version', '?'))
                desc = item.get('advisory', 'Sem descrição')
                findings.append({
                    'tool': 'SAFETY',
                    'severity': 'HIGH',
                    'message': f"Vulnerabilidade em {pkg} ({ver}): {desc}",
                    'file': 'requirements.txt',
                    'line': 0
                })
            return findings
        except json.JSONDecodeError: return []
    except Exception as e:
        logger.add_finding('ERROR', f"Erro ao executar Safety: {e}")
        return []

@click.command('security')
@click.pass_context
@click.argument('target', default='.')
@click.option('--sast', is_flag=True, help="Executa apenas análise estática (Bandit).")
@click.option('--sca', is_flag=True, help="Executa apenas análise de dependências (Safety).")
def security(ctx, target, sast, sca):
    """Realiza auditoria de segurança (SAST + SCA)."""
    with ExecutionLogger('security', target, ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SECURITY] Auditoria de Segurança em '{target}' ---")
        run_all = not (sast or sca)
        findings = []

        bandit_path = _get_tool_path('bandit')
        safety_path = _get_tool_path('safety')

        if not bandit_path and (run_all or sast):
             click.echo(Fore.RED + "[AVISO] 'bandit' não encontrado.")
        if not safety_path and (run_all or sca):
             click.echo(Fore.RED + "[AVISO] 'safety' não encontrado.")

        if (run_all or sast) and bandit_path: findings.extend(_run_bandit(target, logger))
        if (run_all or sca) and safety_path: findings.extend(_run_safety(logger))

        if not findings:
            if bandit_path or safety_path: click.echo(Fore.GREEN + "\n[OK] Nenhuma vulnerabilidade conhecida encontrada.")
            return

        click.echo(Fore.RED + Style.BRIGHT + f"\n[ALERTA] {len(findings)} problemas de segurança detectados!")
        for f in findings:
            sev = f['severity'].upper()
            color = Fore.RED if sev in ['HIGH', 'CRITICAL'] else (Fore.YELLOW if sev == 'MEDIUM' else Fore.WHITE)
            click.echo(f"\n{color}[{f['tool']}][{sev}] {f['message']}")
            click.echo(Fore.WHITE + f"   > Em: {f['file']}:{f['line']}")
            if f.get('code'): click.echo(Fore.CYAN + f"   > Código: {f.get('code')}")
            logger.add_finding(severity='CRITICAL' if sev in ['HIGH', 'CRITICAL'] else 'WARNING', category='SECURITY', message=f"[{f['tool']}] {f['message']}", file=f['file'], line=f['line'])
        click.echo(Fore.RED + "\nRecomendação: Revise e corrija estas vulnerabilidades imediatamente.")