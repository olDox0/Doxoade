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
    Retorna o caminho absoluto da ferramenta no venv.
    """
    # 1. Tenta no venv atual
    python_exe = _get_venv_python_executable()
    if python_exe:
        venv_dir = os.path.dirname(python_exe)
        tool_path = os.path.join(venv_dir, tool_name + ('.exe' if os.name == 'nt' else ''))
        if os.path.exists(tool_path):
            return tool_path
            
    # 2. Fallback para PATH global
    return shutil.which(tool_name)

def _check_tool(tool_name):
    return _get_tool_path(tool_name) is not None

def _run_bandit(target, logger):
    """
    Executa SAST com Bandit.
    """
    tool = _get_tool_path('bandit')
    if not tool: 
        click.echo(Fore.RED + "   [ERRO] Executável do Bandit não encontrado.")
        return []
    
    click.echo(Fore.YELLOW + "   > Executando SAST (Bandit)...")
    
    # Exclusões vitais para performance
    # No Windows, caminhos podem precisar de tratamento, mas o bandit aceita nomes de pasta
    excludes = "venv,.git,__pycache__,build,dist,.doxoade_cache,site-packages"
    
    # Monta comando
    cmd = [tool, '-r', target, '-f', 'json', '-q', '-x', excludes]
    
    # Debug: Mostra o comando se necessário (descomente para ver)
    # click.echo(f"   [CMD] {' '.join(cmd)}")
    
    try:
        # Timeout de 120s para segurança
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            timeout=120
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
            
        except json.JSONDecodeError:
            # Bandit não gerou JSON (pode ter crashado ou saída vazia)
            if result.stderr:
                logger.add_finding('WARNING', "Bandit retornou saída inválida", details=result.stderr[:200])
            return []
            
    except subprocess.TimeoutExpired:
        click.echo(Fore.RED + "   [TIMEOUT] Bandit demorou muito e foi abortado.")
        logger.add_finding('ERROR', "Bandit Timeout ( > 120s)")
        return []
    except Exception as e:
        logger.add_finding('ERROR', f"Erro ao executar Bandit: {e}")
        return []

def _run_safety(logger):
    """
    Executa SCA com Safety.
    """
    tool = _get_tool_path('safety')
    if not tool: 
        click.echo(Fore.RED + "   [ERRO] Executável do Safety não encontrado.")
        return []
    
    click.echo(Fore.YELLOW + "   > Executando SCA (Safety)...")
    cmd = [tool, 'check', '--json']

    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace',
            timeout=60
        )
        
        try:
            data = json.loads(result.stdout)
            findings = []
            
            # Safety 2.x/3.x structure handling
            if isinstance(data, dict) and 'vulnerabilities' in data:
                vulns = data['vulnerabilities']
            else:
                vulns = data 
            
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
            
        except json.JSONDecodeError:
            # Safety costuma escrever texto plano se não achar nada ou der erro de API
            return []
            
    except Exception as e:
        logger.add_finding('ERROR', f"Erro ao executar Safety: {e}")
        return []

@click.command('security')
@click.pass_context
@click.argument('target', default='.')
@click.option('--sast', is_flag=True, help="Executa apenas análise estática (Bandit).")
@click.option('--sca', is_flag=True, help="Executa apenas análise de dependências (Safety).")
def security(ctx, target, sast, sca):
    """
    Realiza auditoria de segurança (SAST + SCA).
    """
    with ExecutionLogger('security', target, ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SECURITY] Auditoria de Segurança em '{target}' ---")
        
        run_all = not (sast or sca)
        findings = []

        # 1. SAST (Bandit)
        if run_all or sast:
            findings.extend(_run_bandit(target, logger))

        # 2. SCA (Safety)
        if run_all or sca:
            findings.extend(_run_safety(logger))

        # 3. Relatório
        if not findings:
            click.echo(Fore.GREEN + "\n[OK] Nenhuma vulnerabilidade conhecida encontrada.")
            return

        click.echo(Fore.RED + Style.BRIGHT + f"\n[ALERTA] {len(findings)} problemas de segurança detectados!")
        
        for f in findings:
            sev = f['severity'].upper()
            color = Fore.RED if sev in ['HIGH', 'CRITICAL'] else (Fore.YELLOW if sev == 'MEDIUM' else Fore.WHITE)
            
            click.echo(f"\n{color}[{f['tool']}][{sev}] {f['message']}")
            click.echo(Fore.WHITE + f"   > Em: {f['file']}:{f['line']}")
            if f.get('code'):
                click.echo(Fore.CYAN + f"   > Código: {f.get('code')}")
                
            logger.add_finding(
                severity='CRITICAL' if sev in ['HIGH', 'CRITICAL'] else 'WARNING',
                category='SECURITY',
                message=f"[{f['tool']}] {f['message']}",
                file=f['file'],
                line=f['line']
            )

        click.echo(Fore.RED + "\nRecomendação: Revise e corrija estas vulnerabilidades imediatamente.")