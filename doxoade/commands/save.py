# doxoade/commands/save.py
import sys
import os
from datetime import datetime, timezone
import click
import sqlite3
from colorama import Fore, Style
#import antigravity
from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results,
    _update_open_incidents
)
from .check import run_check_logic

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
            
            corrected_content = _run_git_command(
                ['show', f"{new_commit_hash}:{file_path}"],
                capture_output=True
            )
            
            if not corrected_content:
                continue
    
            cursor.execute(
                "INSERT OR REPLACE INTO solutions (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f_hash, corrected_content, new_commit_hash, project_path, datetime.now(timezone.utc).isoformat(), file_path, incident['message'], incident['line'])
            )
            learned_count += 1


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