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
    _update_open_incidents # <--- IMPORTE A FUNÇÃO AQUI
)
from .check import run_check_logic

def _run_quality_check():
    """Executa a lógica do check em memória e retorna os resultados."""
    try:
        return run_check_logic(path='.', cmd_line_ignore=[], fix=False, debug=False, no_cache=True)
    except Exception as e:
        click.echo(Fore.RED + f"A análise de qualidade falhou com um erro interno: {e}")
        return None

# A função _manage_incidents_and_learn está correta como na nossa penúltima versão.
# Ela deve usar 'diff --cached'.
def _manage_incidents_and_learn(current_results, logger, project_path):
    """Aprende com as correções comparando com incidentes abertos."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes e aprendendo com correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_hashes = {f['hash'] for f in current_results.get('findings', [])}
    
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = [dict(row) for row in cursor.fetchall()]
        
        learned_count = 0
        if open_incidents:
            old_findings_map = {inc['finding_hash']: inc for inc in open_incidents}
            resolved_hashes = set(old_findings_map.keys()) - current_hashes
            
            if resolved_hashes:
                click.echo(Fore.WHITE + f"   > {len(resolved_hashes)} problema(s) resolvido(s) detectado(s).")
                for f_hash in resolved_hashes:
                    incident = old_findings_map[f_hash]
                    diff_output = _run_git_command(
                        ['diff', '--cached', incident['commit_hash'], '--', incident['file_path']],
                        capture_output=True
                    )
                    if not diff_output: continue

                    cursor.execute(
                        "INSERT OR REPLACE INTO solutions (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (f_hash, diff_output, "PENDING_COMMIT", project_path, datetime.now(timezone.utc).isoformat(), incident['file_path'], incident['message'])
                    )
                    learned_count += 1
        
        if not current_hashes:
             cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))

        conn.commit()

        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhuma solução nova aprendida neste commit.")

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

        # CAMINHO DA FALHA
        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            # A LÓGICA CRÍTICA: Se falhar, o save registra os incidentes.
            _update_open_incidents(check_results, project_path)
            _present_results('text', check_results)
            _run_git_command(['reset'])
            sys.exit(1)
        
        # CAMINHO DO SUCESSO
        # A lógica de aprendizado só é executada se o check passar.
        _manage_incidents_and_learn(check_results, logger, project_path)

        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
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