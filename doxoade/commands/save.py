# doxoade/commands/save.py
import sys
import os
from datetime import datetime, timezone
import click
from colorama import Fore, Style
import sqlite3
#import antigravity
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

def _manage_incidents_and_learn(new_commit_hash, logger, project_path):
    """(Arquitetura Finalíssima) Compara incidentes antigos com o novo commit para aprender."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes e aprendendo com correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = [dict(row) for row in cursor.fetchall()]
        
        learned_count = 0
        if open_incidents:
            # Como o commit foi bem-sucedido, presumimos que todos os incidentes abertos foram resolvidos.
            click.echo(Fore.WHITE + f"   > {len(open_incidents)} problema(s) resolvido(s) detectado(s).")
            for incident in open_incidents:
                f_hash = incident['finding_hash']
                file_path = incident['file_path']
                incident_commit = incident['commit_hash']
                
                # LÓGICA DE DIFF FINAL: Compara o commit do erro com o novo commit da correção.
                # Esta é a forma mais robusta e à prova de falhas de estado.
                diff_output = _run_git_command(
                    ['diff', incident_commit, new_commit_hash, '--', file_path],
                    capture_output=True
                )
                
                if not diff_output:
                    continue

                message = incident.get('message', 'Mensagem não registrada.') 
                cursor.execute(
                    "INSERT OR REPLACE INTO solutions (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f_hash, diff_output, new_commit_hash, project_path, datetime.now(timezone.utc).isoformat(), file_path, message)
                )
                learned_count += 1

        # Limpa todos os incidentes abertos, pois o commit foi um sucesso.
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
    arguments = ctx.params
    with ExecutionLogger('save', '.', arguments) as logger:
        project_path = os.getcwd()
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
            _present_results('text', check_results)
            click.echo(Fore.YELLOW + "Execute 'doxoade check .' para registrar os incidentes e ver sugestões.")
            _run_git_command(['reset'])
            sys.exit(1)
        
        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
        _run_git_command(['commit', '-m', message])
        
        # Agora que o commit existe, obtemos seu hash
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        
        # E só então tentamos aprender, usando o hash do novo commit como referência
        if new_commit_hash:
            _manage_incidents_and_learn(new_commit_hash, logger, project_path)

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")