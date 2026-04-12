# -*- coding: utf-8 -*-
# doxoade/commands/utils.py
"""
Utility Commands Facade - v97.0 Platinum.
Compliance: OSL-4, PASC-8.5.
"""
import os
import sys
import re
import json
import textwrap
import sqlite3 # noqa
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
 # Adicione estes imports
from ..shared_tools import (
    _print_finding_details, 
    _get_code_snippet, 
    ExecutionLogger, 
    _find_project_root,
    _run_git_command
)
from ..database import get_db_connection
__version__ = "34.0 Alfa"
@click.command('log')
@click.option('-n', '--lines', 'limit', default=10, help="Limite de findings.")
@click.option('-s', '--snippets', is_flag=True, help="Exibe código.")
def log(limit, snippets):
    """📜 Consulta o histórico de incidentes no banco de dados."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT f.*, e.command, e.project_path, e.timestamp FROM findings f JOIN events e ON f.event_id = e.id ORDER BY e.timestamp DESC LIMIT ?", (limit,))
        findings = cursor.fetchall()
        if not findings:
            click.echo("[-] Nenhum registro encontrado.")
            return
        for row in reversed(findings):
            f_dict = dict(row)
            f_dict['details'] = f"CMD: {f_dict.get('command')} | Data: {f_dict.get('timestamp')}"
            if snippets and f_dict.get('file') and f_dict.get('line'):
                full_p = os.path.join(f_dict.get('project_path', ''), f_dict['file'])
                if os.path.exists(full_p):
                    f_dict['snippet'] = _get_code_snippet(full_p, f_dict['line'])
            _print_finding_details(f_dict)
            print()
    finally: conn.close()
def _build_log_query(search_term, command, file, category, severity, after, before, limit):
    """Especialista em construção de SQL (PASC 8.5). CC reduzida."""
    base = "SELECT f.*, e.command, e.project_path, e.timestamp FROM findings f JOIN events e ON f.event_id = e.id"
    clauses, params = [], []
    if search_term: clauses.append("f.message LIKE ?"); params.append(f"%{search_term}%")
    if command: clauses.append("e.command LIKE ?"); params.append(f"%{command}%")
    if file: clauses.append("f.file LIKE ?"); params.append(f"%{file.replace('\\', '/')}%")
    if category: clauses.append("f.category = ?"); params.append(category.upper())
    if severity: clauses.append("f.severity = ?"); params.append(severity.upper())
    if after: clauses.append("e.timestamp >= ?"); params.append(after)
    if before: clauses.append("e.timestamp <= ?"); params.append(f"{before} 23:59:59")
    query = base + (" WHERE " + " AND ".join(clauses) if clauses else "")
    query += " ORDER BY e.timestamp DESC LIMIT ?"
    params.append(limit)
    return query, params
def _render_log_entry(f_dict, show_snippets):
    """Especialista em UI de Log."""
    f_dict['details'] = f"CMD: {f_dict.get('command')} | Data: {f_dict.get('timestamp')}"
    if show_snippets and f_dict.get('file') and f_dict.get('line'):
        full_p = os.path.join(f_dict.get('project_path', ''), f_dict['file'])
        if os.path.exists(full_p):
            f_dict['snippet'] = _get_code_snippet(full_p, f_dict['line'])
    _print_finding_details(f_dict)
    print()
@click.command('show-trace')
@click.pass_context
@click.argument('filepath', type=click.Path(exists=True, dir_okay=False), required=False)
def show_trace(ctx, filepath):
    """Analisa e exibe um arquivo de trace de sessão (.jsonl) de forma legível."""
    target_file = filepath
    if not target_file:
        click.echo(Fore.CYAN + "Nenhum arquivo especificado. Procurando pelo trace mais recente...")
        target_file = _find_latest_trace_file()
        if not target_file:
            click.echo(Fore.RED + "Nenhum arquivo de trace ('doxoade_trace_*.jsonl') encontrado no diretório atual."); return
        click.echo(Fore.GREEN + f"Encontrado: '{target_file}'")
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TRACE REPLAY] Exibindo sessão de '{target_file}' ---")
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines:
            click.echo(Fore.YELLOW + "O arquivo de trace está vazio."); return
        first_ts = json.loads(lines[0]).get('ts', 0)
        
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                stream = entry.get('stream', 'unknown')
                data = entry.get('data', '').rstrip('\n')
                
                relative_time = ts - first_ts
                
                color = Fore.YELLOW
                if stream == 'stdout': color = Fore.GREEN
                elif stream == 'stderr': color = Fore.RED
                
                click.echo(color + f"[{relative_time:8.3f}s] [{stream.upper():<6}] " + Style.RESET_ALL + data)
            except (json.JSONDecodeError, KeyError):
                click.echo(Fore.RED + f"[ERRO] Linha malformada no arquivo de trace: {line.strip()}")
                continue
                
    except Exception as e:
        click.echo(Fore.RED + f"Falha ao processar o arquivo de trace: {e}")
    pass # Placeholder
@click.command('mk')
@click.argument('items', nargs=-1)
@click.option('--path', '-p', 'base_path', default='.', type=click.Path(exists=True))
@click.option('--architecture', '-a', type=click.Path(exists=True))
@click.option('--tree', '-t', is_flag=True)
def mk(base_path, items, architecture, tree):
    """🔨 Construtor de Topologia e Visualizador Nexus."""
    from .mk_systems.mk_commands import execute_mk_logic
    execute_mk_logic(base_path, items, architecture, tree)
@click.command('create-pipeline')
@click.pass_context
@click.argument('filename')
@click.argument('commands', nargs=-1, required=True)
def create_pipeline(ctx, filename, commands):
    """Cria um arquivo de pipeline (.dox) com uma sequência de comandos."""
    """
    Cria um arquivo de pipeline (.dox) com uma sequência de comandos.
    Cada comando deve ser passado como um argumento separado e entre aspas.
    Exemplo:
      doxoade create-pipeline deploy.dox "doxoade health" "doxoade save 'Deploy final' --force"
    """
    click.echo(Fore.CYAN + f"--- [CREATE-PIPELINE] Criando arquivo de pipeline: {filename} ---")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Pipeline gerado pelo doxoade em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for command in commands:
                f.write(f"{command}\n")
        
        click.echo(Fore.GREEN + f"[OK] Pipeline '{filename}' criado com sucesso com {len(commands)} passo(s).")
        click.echo(Fore.YELLOW + f"Agora você pode executá-lo com: doxoade auto --file {filename}")
    except IOError as e:
        click.echo(Fore.RED + f"[ERRO] Não foi possível escrever no arquivo '{filename}': {e}")
        sys.exit(1)
    pass # Placeholder
# Funções auxiliares (copie-as para este arquivo também)
def _display_log_entry(cursor, event, index, total, show_snippets=False):
    """Formata e exibe um único evento do banco de dados."""
    ts_local = event['timestamp'] # O timestamp já deve estar em um formato legível
    header = f"--- Entrada de Log #{index}/{total} ({ts_local}) ---"
    click.echo(Fore.CYAN + Style.BRIGHT + header)
    click.echo(Fore.WHITE + f"Comando: {event['command']} (Doxoade v{event['doxoade_version']})")
    click.echo(Fore.WHITE + f"Projeto: {event['project_path']}")
    click.echo(Fore.WHITE + Style.DIM + f"Tempo: {event['execution_time_ms']:.2f}ms")
    # Busca os 'findings' associados a este evento
    cursor.execute("SELECT * FROM findings WHERE event_id = ?", (event['id'],))
    findings = cursor.fetchall()
    if not findings:
        click.echo(Fore.GREEN + "Resultado: Nenhum problema encontrado nesta execução.")
    else:
        summary_text = f"Resultado: {len(findings)} problema(s) encontrado(s)."
        click.echo(Fore.YELLOW + summary_text)
        click.echo(Fore.WHITE + "Detalhes dos Problemas:")
        for finding in findings:
            finding_dict = dict(finding)
            
            # --- NOVA LÓGICA DE SNIPPET SOB DEMANDA ---
            if show_snippets and finding_dict.get('file') and finding_dict.get('line'):
                # O caminho do arquivo no DB é relativo, precisamos do caminho absoluto do projeto
                project_path = event['project_path']
                full_file_path = os.path.join(project_path, finding_dict['file'])
                
                # Se o arquivo ainda existir, recalcula o snippet
                if os.path.exists(full_file_path):
                    snippet = _get_code_snippet(full_file_path, finding_dict['line'])
                    if snippet:
                        finding_dict['snippet'] = snippet # Adiciona ao dicionário antes de imprimir
            # --- FIM DA NOVA LÓGICA ---
            _print_finding_details(finding_dict)
    
    click.echo("")
    pass
def _find_latest_trace_file():
    try:
        trace_dir = Path.home() / '.doxoade' / 'traces'
        if not trace_dir.exists():
            return None
            
        trace_files = list(trace_dir.glob('trace_*.jsonl'))
        if not trace_files:
            return None
            
        latest_file = max(trace_files, key=lambda p: p.stat().st_mtime)
        return str(latest_file)
    except Exception:
        return None
    pass
@click.command('setup-regression')
def setup_regression():
    """Cria a estrutura de diretórios e arquivos para os testes de regressão."""
    click.echo(Fore.CYAN + "--- [SETUP-REGRESSION] Configurando o ambiente do Projeto Cânone ---")
    
    base_dir = "regression_tests"
    fixtures_dir = os.path.join(base_dir, "fixtures")
    canon_dir = os.path.join(base_dir, "canon")
    
    patient_zero_project = os.path.join(fixtures_dir, "project_syntax_error")
    # Usamos textwrap para um código mais limpo
    patient_zero_code = "def func():\\n    pass # Erro de indentacao"
    canon_toml_content = textwrap.dedent("""
        # Define os casos de teste para o sistema de regressão.
        [[test_case]]
        id = "check_finds_syntax_error"
        command = "doxoade check ."
        project = "project_syntax_error"
    """)
    
    try:
        os.makedirs(patient_zero_project, exist_ok=True)
        os.makedirs(canon_dir, exist_ok=True)
        
        with open(os.path.join(patient_zero_project, "main.py"), "w", encoding="utf-8") as f:
            f.write(patient_zero_code)
        
        with open(os.path.join(base_dir, "canon.toml"), "w", encoding="utf-8") as f:
            f.write(canon_toml_content)
            
        click.echo(Fore.GREEN + "   > [OK] Estrutura de regressão simplificada criada com sucesso.")
        
    except OSError as e:
        click.echo(Fore.RED + f"\\n[ERRO] Falha ao criar a estrutura de diretórios: {e}")
        sys.exit(1)
        
# -----------------------------------------------------------------------------
# COMANDOS DA CLI (ARQUITETURA FINAL E ROBUSTA)
# -----------------------------------------------------------------------------
@click.command('setup-health')
@click.argument('path', default='.')
@click.pass_context
def setup_health_cmd(ctx, path):
    """🛡️ Inicializa protocolos de saúde no projeto."""
    root = _find_project_root(os.path.abspath(path))
    click.echo(Fore.CYAN + f"--- [SETUP-HEALTH] Configurando '{os.path.basename(root)}' ---")
    
    with ExecutionLogger('setup-health', root, ctx.params) as _:
        # 1. Venv
        venv_path = os.path.join(root, 'venv')
        if not os.path.exists(venv_path):
            click.echo(Fore.YELLOW + "   > Criando venv...")
            import subprocess
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)
        
        # 2. TOML
        pyproject_path = os.path.join(root, 'pyproject.toml')
        if not os.path.exists(pyproject_path):
            with open(pyproject_path, 'w', encoding='utf-8') as f:
                f.write('[tool.doxoade]\nignore = [\"venv/\", \".git/\", \"__pycache__/\"]\nsource_dir = \".\"\n')
        
        click.secho("✅ Estado de Ouro configurado.", fg='green', bold=True)
   
# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
def _get_github_repo_info():
    try:
        url = _run_git_command(['remote', 'get-url', 'origin'], capture_output=True)
        if not url: return "unknown/unknown"
        match = re.search(r'github\.com[:/]([\w-]+)/([\w-]+)', url)
        if match: return f"{match.group(1)}/{match.group(2)}"
    except Exception as e:
        import sys, os
        _, exc_obj, exc_tb = sys.exc_info()
        f_name = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _get_github_repo_info\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    return "unknown/unknown"
# -----------------------------------------------------------------------------
# FUNÇÕES DE APRESENTAÇÃO E DIAGNÓSTICO
# -----------------------------------------------------------------------------
def _analyze_traceback(stderr_output):
    diagnostics = {
        "ModuleNotFoundError": "Erro de importação. Lib não instalada no venv.",
        "AttributeError": "Erro de atributo. Cheque digitação ou versão da API.",
        "FileNotFoundError": "Arquivo não encontrado. Verifique caminhos e escapes."
    }
    click.echo(Fore.YELLOW + "\n--- [DIAGNÓSTICO] ---")
    for key, message in diagnostics.items():
        if key in stderr_output:
            click.echo(Fore.CYAN + f"[PADRÃO DETECTADO] {message}"); return
    click.echo(Fore.CYAN + "Analise o traceback acima para detalhes.")