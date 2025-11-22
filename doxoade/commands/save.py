# doxoade/commands/save.py
#import subprocess
import sys
import sqlite3
import re
import os
import click
from datetime import datetime, timezone
from colorama import Fore, Style
from ..database import get_db_connection
#import antigravity
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results,
    _update_open_incidents
)
from .check import run_check_logic

def _get_staged_python_files(git_root):
    """Retorna uma lista de caminhos absolutos de arquivos .py no staging area."""
    # --diff-filter=AMR -> Apenas arquivos Adicionados, Modificados, Renomeados
    staged_files_str = _run_git_command(
        ['diff', '--name-only', '--cached', '--diff-filter=AMR', '--', '*.py'], 
        capture_output=True
    )
    if not staged_files_str:
        return []
    
    # Converte os caminhos relativos do Git em caminhos absolutos
    return [os.path.join(git_root, f.strip()) for f in staged_files_str.splitlines()]

def _run_quality_check():
    """Executa a lógica do check em memória e retorna os resultados."""
    try:
        return run_check_logic(path='.', cmd_line_ignore=[], fix=False, debug=False, no_cache=True)
    except Exception as e:
        click.echo(Fore.RED + f"A análise de qualidade falhou com um erro interno: {e}")
        return None

def _learn_from_saved_commit(new_commit_hash, logger, project_path):
    """(V8 Final) Aprende soluções concretas e templates de forma transacional."""
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
        
        for incident in open_incidents:
            diff_output = _run_git_command(
                ['diff', incident['commit_hash'], new_commit_hash, '--', incident['file_path']],
                capture_output=True, silent_fail=True
            )
            
            if diff_output:
                # 1. Aprende a solução concreta
                cursor.execute(
                    "INSERT OR REPLACE INTO solutions (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (incident['finding_hash'], 
                     _run_git_command(['show', f"{new_commit_hash}:{incident['file_path']}"], capture_output=True, silent_fail=True), 
                     new_commit_hash, project_path, datetime.now(timezone.utc).isoformat(), 
                     incident['file_path'], incident['message'], incident.get('line'))
                )
                learned_solutions += 1

                # 2. TENTA APRENDER O TEMPLATE
                if _abstract_and_learn_template(cursor, incident):
                    learned_templates += 1

        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
        conn.commit()

        if learned_solutions > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_solutions} solução(ões) concreta(s) aprendida(s).")
        if learned_templates > 0:
            click.echo(Fore.GREEN + f"[Gênese] {learned_templates} template(s) de solução aprendido(s)/reforçado(s).")
        
        if learned_solutions == 0:
            click.echo(Fore.WHITE + "   > Nenhuma solução nova foi aprendida (nenhuma mudança detectada nos arquivos com erro).")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao aprender com as correções.", details=str(e))
    finally:
        if 'conn' in locals() and conn: conn.close()

def _abstract_and_learn_template(cursor, concrete_finding):
    """Analisa um 'finding' e tenta criar/atualizar um template de solução."""
    message = concrete_finding.get('message', '')
    category = concrete_finding.get('category', '')
    
    click.echo(Fore.MAGENTA + f"   > [Debug Gênese] Tentando abstrair: msg='{message}', cat='{category}'")
    
    problem_pattern = None
    solution_template = "REMOVE_LINE" 
    
    if re.match(r"'(.*?)' imported but unused", message) and category == 'DEADCODE':
        problem_pattern = "'<MODULE>' imported but unused"
    elif re.match(r"redefinition of unused '(.*?)' from line", message) and category == 'DEADCODE':
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
        
        if "nothing to commit" in (_run_git_command(['status', '--porcelain'], capture_output=True) or ""):
             click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return

        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade...")
        check_results = run_check_logic('.', [], False, False, no_cache=True)
        
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
                target_files=files_to_check # <-- Passa apenas os arquivos modificados
            )
        
        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
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