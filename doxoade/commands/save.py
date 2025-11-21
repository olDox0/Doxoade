# doxoade/commands/save.py
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
    """Compara incidentes abertos com o novo commit para aprender soluções."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes resolvidos... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = [dict(row) for row in cursor.fetchall()]
        
        if not open_incidents:
            click.echo(Fore.WHITE + "   > Nenhum incidente aberto encontrado para aprender.")
            return

        learned_count = 0
        click.echo(Fore.WHITE + f"   > {len(open_incidents)} incidente(s) aberto(s) encontrado(s). Verificando se foram resolvidos...")
        for incident in open_incidents:
            f_hash = incident['finding_hash']
            file_path = incident['file_path'] 
            
            learned_this_loop = False

            corrected_content = _run_git_command(
                ['show', f"{new_commit_hash}:{file_path}"],
                capture_output=True
            )
            
            if not corrected_content:
                continue
    
            cursor.execute(
                "INSERT OR REPLACE INTO solutions (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f_hash, corrected_content, new_commit_hash, project_path, datetime.now(timezone.utc).isoformat(), file_path, incident['message'], incident.get('line')) # use .get('line') para segurança
            )
            learned_count += 1
            learned_this_loop = True

            if learned_this_loop:
                _abstract_and_learn_template(conn, incident)

        # Limpa todos os incidentes abertos, pois o commit foi um sucesso.
        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
        conn.commit()

        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhuma solução nova foi aprendida neste commit.")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao aprender com as correções.", details=str(e))
    finally:
        conn.close()

def _abstract_and_learn_template(conn, concrete_finding):
    """Analisa um 'finding' concreto e tenta criar um template de solução genérico."""
    message = concrete_finding.get('message', '')
    category = concrete_finding.get('category', '')

    # --- Motor de Regras de Abstração ---
    problem_pattern = None
    solution_template = "REMOVE_LINE" # A maioria das correções simples é remover a linha

    # Regra 1: Imports não utilizados
    match = re.match(r"'(.*?)' imported but unused", message)
    if match and category == 'DEADCODE':
        problem_pattern = "'<MODULE>' imported but unused"
    
    # Regra 2: Redefinições não utilizadas
    match = re.match(r"redefinition of unused '(.*?)' from line", message)
    if match and category == 'DEADCODE':
        problem_pattern = "redefinition of unused '<VAR>' from line"

    # Adicione mais regras aqui para outros tipos de erro...

    if not problem_pattern:
        return # Não sabemos como abstrair este problema ainda

    # Se chegamos aqui, temos um template. Vamos salvá-lo ou atualizá-lo.
    cursor = conn.cursor()
    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (problem_pattern,))
    existing = cursor.fetchone()

    if existing:
        # O template já existe, aumentamos a confiança
        new_confidence = existing['confidence'] + 1
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_confidence, existing['id']))
    else:
        # Novo template, inserimos com confiança inicial
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (problem_pattern, solution_template, category, datetime.now(timezone.utc).isoformat())
        )
    conn.commit()

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