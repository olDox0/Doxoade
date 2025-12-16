# doxoade/commands/security.py
import sys
import subprocess
import shutil
import os
import json
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_venv_python_executable, _get_project_config

# Mapeamento para comparação de severidade
SEVERITY_MAP = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

def _get_tool_path(tool_name):
    """
    Localiza o executável da ferramenta de segurança.
    """
    tool_exe = tool_name + ('.exe' if os.name == 'nt' else '')
    
    # 1. Busca no Venv do Projeto Alvo
    target_python = _get_venv_python_executable()
    if target_python:
        target_venv_dir = os.path.dirname(target_python)
        for sub in ['', 'Scripts', 'bin']:
            path = os.path.join(target_venv_dir, sub, tool_exe)
            if os.path.exists(path): return path

    # 2. Busca no Ambiente do Interpretador Atual
    current_python_dir = os.path.dirname(sys.executable)
    possible_dirs = [
        current_python_dir,
        os.path.join(current_python_dir, 'Scripts'),
        os.path.join(current_python_dir, 'bin')
    ]
    for d in possible_dirs:
        path = os.path.join(d, tool_exe)
        if os.path.exists(path): return path

    # 3. Busca Baseada na Localização do Código Fonte
    try:
        current_file = os.path.abspath(__file__)
        pkg_dir = os.path.dirname(os.path.dirname(current_file))
        root_dir = os.path.dirname(pkg_dir)
        
        source_venv_dirs = [
            os.path.join(root_dir, 'venv', 'Scripts'),
            os.path.join(root_dir, 'venv', 'bin')
        ]
        
        for d in source_venv_dirs:
            path = os.path.join(d, tool_exe)
            if os.path.exists(path): 
                return path
    except Exception: pass

    # 4. Fallback para PATH Global
    return shutil.which(tool_name)

def _is_file_ignored(filepath, ignores):
    """
    Verifica manualmente se o arquivo deve ser ignorado.
    """
    filepath = os.path.normpath(filepath)
    parts = filepath.split(os.sep)
    clean_ignores = {os.path.normpath(i).strip(os.sep) for i in ignores}
    
    for part in parts:
        if part in clean_ignores:
            return True
    return False

def _run_bandit(target, logger, config_ignore):
    """Executa o Bandit (SAST) com filtragem dupla."""
    tool = _get_tool_path('bandit')
    if not tool: 
        click.echo(Fore.RED + "   [ERRO] Executável do Bandit não encontrado.")
        return []
    
    # Lista padrão de exclusão de infraestrutura
    system_excludes = [
        "venv", ".git", "__pycache__", "build", "dist", 
        ".doxoade_cache", "site-packages", ".idea", ".vscode", "node_modules",
        "doxoade.egg-info", "tests", "regression_tests"
    ]
    
    # Processa a lista do TOML
    custom_excludes = [item.strip('/\\') for item in config_ignore]
    
    # Combina para passar ao Bandit (Melhor esforço)
    final_excludes = list(set(system_excludes + custom_excludes))
    excludes_str = ",".join(final_excludes)
    
    click.echo(Fore.YELLOW + f"   > Executando SAST (Bandit)... (Ignorando: {len(final_excludes)} diretórios)")
    
    # -r: recursivo, -f: json
    cmd = [tool, '-r', target, '-f', 'json', '-q', '-x', excludes_str]
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120
        )
        try:
            data = json.loads(result.stdout)
            findings = []
            skipped_count = 0
            
            for item in data.get('results', []):
                filename = item.get('filename', '')
                
                # Aplica o filtro manual de pastas
                if _is_file_ignored(filename, final_excludes):
                    skipped_count += 1
                    continue

                findings.append({
                    'tool': 'BANDIT',
                    'severity': item['issue_severity'],
                    'confidence': item['issue_confidence'],
                    'message': item['issue_text'],
                    'file': filename,
                    'line': item['line_number'],
                    'code': item['code'].strip()
                })
            
            if skipped_count > 0:
                click.echo(Fore.WHITE + Style.DIM + f"   > Filtragem: {skipped_count} alertas ignorados (pastas de teste/venv).")
                
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
            
            vulns = []
            if isinstance(data, dict) and 'vulnerabilities' in data:
                vulns = data['vulnerabilities']
            elif isinstance(data, list):
                vulns = data
            
            for item in vulns:
                pkg = item.get('package_name', item.get('name', 'unknown'))
                ver = item.get('installed_version', item.get('version', '?'))
                desc = item.get('advisory', 'Sem descrição')
                # Vulnerabilidades de dependência são consideradas HIGH por padrão
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
@click.option('--level', '-l', type=click.Choice(['LOW', 'MEDIUM', 'HIGH']), default='LOW', help="Filtra resultados por severidade mínima.")
def security(ctx, target, sast, sca, level):
    """Realiza auditoria de segurança (SAST + SCA)."""
    
    with ExecutionLogger('security', target, ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SECURITY] Auditoria de Segurança em '{target}' ---")
        click.echo(Fore.WHITE + Style.DIM + f"   > Nível de filtro: {level}+")
        
        config = _get_project_config(logger, start_path=target)
        config_ignore = config.get('ignore', [])
        
        run_all = not (sast or sca)
        findings = []

        bandit_path = _get_tool_path('bandit')
        safety_path = _get_tool_path('safety')

        if not bandit_path and (run_all or sast): click.echo(Fore.RED + "[AVISO] 'bandit' não encontrado.")
        if not safety_path and (run_all or sca): click.echo(Fore.RED + "[AVISO] 'safety' não encontrado.")

        if (run_all or sast) and bandit_path: 
            findings.extend(_run_bandit(target, logger, config_ignore))
            
        if (run_all or sca) and safety_path: 
            findings.extend(_run_safety(logger))

        # --- FILTRAGEM POR SEVERIDADE ---
        target_val = SEVERITY_MAP.get(level, 1)
        visible_findings = []
        hidden_count = 0

        for f in findings:
            sev = f['severity'].upper()
            f_val = SEVERITY_MAP.get(sev, 1)
            
            if f_val >= target_val:
                visible_findings.append(f)
            else:
                hidden_count += 1

        if not visible_findings:
            if hidden_count > 0:
                click.echo(Fore.GREEN + f"\n[OK] Nenhum problema de nível {level} ou superior encontrado.")
                click.echo(Fore.WHITE + Style.DIM + f"     ({hidden_count} problemas de menor severidade ignorados).")
            else:
                click.echo(Fore.GREEN + "\n[OK] Nenhuma vulnerabilidade conhecida encontrada.")
            return

        click.echo(Fore.RED + Style.BRIGHT + f"\n[ALERTA] {len(visible_findings)} problemas detectados (Filtro: {level}+)!")
        if hidden_count > 0:
            click.echo(Fore.WHITE + Style.DIM + f"         (Ocultando {hidden_count} problemas menores)")

        for f in visible_findings:
            sev = f['severity'].upper()
            color = Fore.RED if sev in ['HIGH', 'CRITICAL'] else (Fore.YELLOW if sev == 'MEDIUM' else Fore.WHITE)
            
            click.echo(f"\n{color}[{f['tool']}][{sev}] {f['message']}")
            click.echo(Fore.WHITE + f"   > Em: {f['file']}:{f['line']}")
            if f.get('code'): click.echo(Fore.CYAN + f"   > Código: {f.get('code')}")
            
            # Loga no banco apenas se for relevante
            log_sev = 'CRITICAL' if sev in ['HIGH', 'CRITICAL'] else 'WARNING'
            logger.add_finding(
                severity=log_sev, 
                category='SECURITY', 
                message=f"[{f['tool']}] {f['message']}", 
                file=f['file'], 
                line=f['line']
            )
            
        click.echo(Fore.RED + "\nRecomendação: Revise e corrija estas vulnerabilidades imediatamente.")