# doxoade/commands/save.py
#import calendar
import sys
import sqlite3
import re
import os
import click
from datetime import datetime, timezone
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results,
    _update_open_incidents
)
from .check import run_check_logic

def _get_staged_python_files(git_root):
    """Retorna uma lista de caminhos absolutos de arquivos .py no staging area."""
    staged_files_str = _run_git_command(
        ['diff', '--name-only', '--cached', '--diff-filter=AMR', '--', '*.py'], 
        capture_output=True
    )
    if not staged_files_str:
        return []
    return [os.path.join(git_root, f.strip()) for f in staged_files_str.splitlines()]

def _run_quality_check():
    """Executa a lógica do check em memória e retorna os resultados."""
    try:
        return run_check_logic(path='.', cmd_line_ignore=[], fix=False, debug=False, no_cache=True)
    except Exception as e:
        click.echo(Fore.RED + f"A análise de qualidade falhou com um erro interno: {e}")
        return None

def _learn_from_saved_commit(new_commit_hash, logger, project_path):
    """(V9 - Corrigido) Aprende soluções concretas e templates de forma transacional."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes resolvidos... ---")
    
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = [dict(row) for row in cursor.fetchall()]
        
        if not open_incidents:
            click.echo(Fore.WHITE + "   > Nenhum incidente aberto para aprender.")
            return

        learned_solutions = 0
        learned_templates = 0
        
        # Obtém a lista de arquivos modificados neste commit
        modified_files_str = _run_git_command(
            ['diff-tree', '--no-commit-id', '--name-only', '-r', new_commit_hash],
            capture_output=True, silent_fail=True
        ) or ""
        modified_files = set(f.strip().replace('\\', '/') for f in modified_files_str.splitlines())
        
        click.echo(Fore.WHITE + f"   > Arquivos modificados neste commit: {modified_files}")
        click.echo(Fore.WHITE + f"   > Incidentes abertos: {len(open_incidents)}")
        
        for incident in open_incidents:
            incident_file = incident['file_path'].replace('\\', '/')
            
            # Verifica se o arquivo do incidente foi modificado neste commit
            if incident_file not in modified_files:
                click.echo(Fore.YELLOW + f"   > Arquivo '{incident_file}' não foi modificado neste commit. Pulando.")
                continue
            
            # Obtém o conteúdo corrigido do arquivo
            corrected_content = _run_git_command(
                ['show', f"{new_commit_hash}:{incident_file}"],
                capture_output=True, silent_fail=True
            )
            
            if not corrected_content:
                click.echo(Fore.YELLOW + f"   > Não foi possível obter o conteúdo de '{incident_file}'.")
                continue
            
            # 1. Aprende a solução concreta
            cursor.execute(
                "INSERT OR REPLACE INTO solutions (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (incident['finding_hash'], 
                 corrected_content, 
                 new_commit_hash, 
                 project_path, 
                 datetime.now(timezone.utc).isoformat(), 
                 incident['file_path'], 
                 incident['message'], 
                 incident.get('line'))
            )
            learned_solutions += 1
            click.echo(Fore.GREEN + f"   > Solução aprendida para: {incident['message'][:50]}...")

            # 2. TENTA APRENDER O TEMPLATE
            if _abstract_and_learn_template(cursor, incident):
                learned_templates += 1

        # Limpa todos os incidentes dos arquivos que foram modificados
        for incident in open_incidents:
            incident_file = incident['file_path'].replace('\\', '/')
            if incident_file in modified_files:
                cursor.execute(
                    "DELETE FROM open_incidents WHERE finding_hash = ? AND project_path = ?", 
                    (incident['finding_hash'], project_path)
                )
        
        conn.commit() 

        if learned_solutions > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_solutions} solução(ões) concreta(s) aprendida(s).")
        if learned_templates > 0:
            click.echo(Fore.GREEN + f"[Gênese] {learned_templates} template(s) de solução aprendido(s)/reforçado(s).")
        
        if learned_solutions == 0:
            click.echo(Fore.WHITE + "   > Nenhuma solução nova foi aprendida (arquivos com erro não foram modificados).")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao aprender com as correções.", details=str(e))
        import traceback
        click.echo(Fore.RED + f"   > [DEBUG] Traceback: {traceback.format_exc()}")
    finally:
        if 'conn' in locals() and conn: conn.close()

def _abstract_and_learn_template(cursor, concrete_finding):
    """Analisa um 'finding' e tenta criar/atualizar um template de solução."""
    message = concrete_finding.get('message', '')
    category = concrete_finding.get('category', '')
    
    # Se a categoria está vazia, tenta inferir do tipo de mensagem
    if not category:
        if 'imported but unused' in message or 'redefinition of unused' in message:
            category = 'DEADCODE'
        elif 'undefined name' in message:
            category = 'RUNTIME-RISK'
        else:
            category = 'UNCATEGORIZED'
    
    click.echo(Fore.MAGENTA + f"   > [Debug Gênese] Tentando abstrair: msg='{message}', cat='{category}'")
    
    problem_pattern = None
    solution_template = "REMOVE_LINE" 
    
    # Regras de abstração
    if re.match(r"'(.*?)' imported but unused", message):
        problem_pattern = "'<MODULE>' imported but unused"
    elif re.match(r"redefinition of unused '(.*?)' from line", message):
        problem_pattern = "redefinition of unused '<VAR>' from line"

    if not problem_pattern:
        click.echo(Fore.YELLOW + "   > [Debug Gênese] Nenhuma regra de abstração correspondeu.")
        return False

    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (problem_pattern,))
    existing = cursor.fetchone()

    if existing:
        new_confidence = existing['confidence'] + 1
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_confidence, existing['id']))
        click.echo(Fore.CYAN + f"   > [Gênese] Confiança do template '{problem_pattern}' aumentada para {new_confidence}.")
    else:
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (problem_pattern, solution_template, category, datetime.now(timezone.utc).isoformat())
        )
        click.echo(Fore.CYAN + f"   > [Gênese] Novo template aprendido: '{problem_pattern}'")
    
    return True

@click.command('save')
@click.pass_context
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo se o 'check' encontrar erros.")
def save(ctx, message, force):
    """Executa um 'commit seguro', aprendendo com as correções e protegendo o repositório."""
    project_path = os.getcwd()
    with ExecutionLogger('save', project_path, ctx.params) as logger:
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos (git add .)...")
        _run_git_command(['add', '.'])
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")
        
        status_output = _run_git_command(['status', '--porcelain'], capture_output=True) or ""
        if not status_output.strip():
             click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar.")
             return

        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade...")
        
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True)
        files_to_check = _get_staged_python_files(git_root)
        
        if not files_to_check:
            click.echo(Fore.GREEN + "[OK] Nenhuma modificação em arquivos Python para verificar.")
            check_results = {'summary': {}, 'findings': []}
        else:
            click.echo(f"   > Analisando {len(files_to_check)} arquivo(s) modificado(s)...")
            check_results = run_check_logic(
                '.', [], False, False, 
                no_cache=True, 
                target_files=files_to_check
            )
        
        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            # IMPORTANTE: Registra os incidentes ANTES de abortar
            _update_open_incidents(check_results, project_path)
            _present_results('text', check_results)
            _run_git_command(['reset'])
            sys.exit(1)
        
        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
        _run_git_command(['commit', '-m', message])
        
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        
        if new_commit_hash:
            _learn_from_saved_commit(new_commit_hash, logger, project_path)

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")