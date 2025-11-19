# doxoade/commands/save.py
import sys
import os
#import json
from datetime import datetime, timezone
import click
from colorama import Fore, Style
#import tempfile

from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _run_git_command, _present_results
from .check import run_check_logic

def _run_quality_check():
    """Executa a lógica do check em memória e retorna os resultados."""
    try:
        return run_check_logic(path='.', cmd_line_ignore=[], fix=False, debug=False, no_cache=True)
    except Exception as e:
        click.echo(Fore.RED + f"A análise de qualidade falhou com um erro interno: {e}")
        return None

def _manage_incidents_and_learn(current_results, logger, project_path):
    """(Versão Definitiva) Gerencia incidentes e aprende comparando com o commit do incidente."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes e aprendendo com correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = cursor.fetchall()
        
        current_findings = current_results.get('findings', [])
        current_hashes = {f['hash'] for f in current_findings}
        
        learned_count = 0
        if open_incidents:
            old_findings_map = {inc['finding_hash']: inc for inc in open_incidents}
            resolved_hashes = set(old_findings_map.keys()) - current_hashes
            
            if resolved_hashes:
                click.echo(Fore.WHITE + f"   > {len(resolved_hashes)} problema(s) resolvido(s) detectado(s).")
                for f_hash in resolved_hashes:
                    incident = old_findings_map[f_hash]
                    file_path = incident['file_path']
                    diff_output = _run_git_command(['diff', '--staged', 'HEAD', '--', file_path], capture_output=True)
                    
                    if not diff_output: continue

                    message = incident['message']
                    cursor.execute(
                        "INSERT OR REPLACE INTO solutions (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (f_hash, diff_output, "PENDING_COMMIT", project_path, datetime.now(timezone.utc).isoformat(), file_path, message)
                    )
                    learned_count += 1
        
        # Lógica de atualização do DB
        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
        if current_findings:
            commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True) or "N/A"
            incidents_to_add = [
                (f.get('hash'), f.get('file'), f.get('message'), commit_hash, datetime.now(timezone.utc).isoformat(), project_path)
                for f in current_findings if f.get('hash')
            ]
            if incidents_to_add:
                cursor.executemany("INSERT OR REPLACE INTO open_incidents (finding_hash, file_path, message, commit_hash, timestamp, project_path) VALUES (?, ?, ?, ?, ?, ?)", incidents_to_add)

        conn.commit()

        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhuma solução aprendida neste commit.")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao gerenciar incidentes.", details=str(e))
    finally:
        conn.close()

@click.command('save')
@click.pass_context
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo se o 'check' encontrar erros.")
def save(ctx, message, force):
    """Executa um 'commit seguro', aprendendo com as correções e protegendo o repositório."""
    arguments = ctx.params
    with ExecutionLogger('save', '.', arguments) as logger:
        project_path = os.getcwd()
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        _run_git_command(['add', '.'])
        
        check_results = _run_quality_check()
        if check_results is None:
            sys.exit(1)
        
        _manage_incidents_and_learn(check_results, logger, project_path)

        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            _present_results('text', check_results)
            _run_git_command(['reset'])
            sys.exit(1)
        
        if "nothing to commit" in (_run_git_command(['status', '--porcelain'], capture_output=True) or ""):
             click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return
        _run_git_command(['commit', '-m', message])
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        if new_commit_hash:
            conn = get_db_connection()
            try:
                conn.execute("UPDATE solutions SET commit_hash = ? WHERE commit_hash = 'PENDING_COMMIT' AND project_path = ?", (new_commit_hash, project_path))
                conn.commit()
            finally:
                conn.close()

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")