# doxoade/commands/save.py
import sys
import subprocess
import shutil
import os
import json
from datetime import datetime, timezone
import click
from colorama import Fore, Style

from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command,
    _present_results
)

def _run_quality_check(logger):
    """Executa 'doxoade check' e retorna os resultados como um dicionário."""
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path:
        return None, "Runner 'doxoade' não encontrado no PATH."
    
    check_command = [runner_path, 'check', '.', '--format', 'json']
    result = subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"A análise de qualidade falhou ou produziu uma saída inválida.\n{result.stderr}"

def _can_proceed_with_commit(check_result, force_flag, logger):
    output = check_result.stdout
    if check_result.returncode == 0:
        click.echo(Fore.GREEN + "[OK] Verificação de qualidade concluída.")
        return True

    # --- A NOVA LÓGICA INTELIGENTE ---
    if force_flag:
        click.echo(Fore.YELLOW + "\n[AVISO] A verificação de qualidade encontrou erros, mas a flag --force foi usada.")
        click.echo(Fore.YELLOW + "Prosseguindo com o commit sob a responsabilidade do usuário.")
        logger.add_finding('warning', "Commit forçado apesar dos erros do 'check'.", details=output)
        return True
        
    # Se não houver --force, o comportamento normal é abortar.
    logger.add_finding('error', "Commit abortado devido a erros do 'check'.", details=output)
    click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
    print(output.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    return False

def _learn_from_fixes(current_results, logger, project_path):
    """Verifica o DB por incidentes abertos e aprende com os que foram resolvidos."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Analisando correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = cursor.fetchall()
        if not open_incidents:
            click.echo(Fore.WHITE + "Nenhum incidente aberto encontrado no banco de dados para este projeto.")
            return

        current_hashes = {f['hash'] for f in current_results.get('findings', [])}
        
        learned_count = 0
        for incident in open_incidents:
            finding_hash = incident['finding_hash']
            if finding_hash not in current_hashes:
                # O problema foi resolvido!
                file_path = incident['file_path']
                diff_output = _run_git_command(['diff', '--staged', '--', file_path], capture_output=True)
                
                if not diff_output: continue # Nenhuma mudança staged para este arquivo
                
                # Salva a solução
                cursor.execute("""
                    INSERT OR REPLACE INTO solutions 
                    (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    finding_hash, diff_output, "PENDING_COMMIT",
                    project_path, datetime.now(timezone.utc).isoformat(), file_path
                ))
                
                # Remove o incidente da tabela de abertos
                cursor.execute("DELETE FROM open_incidents WHERE finding_hash = ?", (finding_hash,))
                learned_count += 1
        
        conn.commit()
        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s) no banco de dados.")
        else:
            click.echo(Fore.WHITE + "Nenhuma das mudanças atuais resolveu um incidente aberto conhecido.")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao processar aprendizado de soluções.", details=str(e))
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

        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        if not _run_git_command(['add', '.']): sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")

        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade ('doxoade check')...")
        check_results, error_msg = _run_quality_check(logger)
        if check_results is None:
            click.echo(Fore.RED + f"[ERRO] {error_msg}"); sys.exit(1)
        
        _learn_from_fixes(check_results, logger, project_path)

        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            logger.add_finding('ERROR', "Commit abortado devido a erros do 'check'.", details=json.dumps(check_results))
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            _present_results('text', check_results)
            # Desfaz o 'git add' para o usuário poder corrigir
            click.echo(Fore.YELLOW + "Desfazendo 'git add' para permitir a correção...")
            _run_git_command(['reset'])
            sys.exit(1)
        
        if has_errors and force:
            logger.add_finding('WARNING', "Commit forçado apesar dos erros do 'check'.")

        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
        commit_output = _run_git_command(['commit', '-m', message], capture_output=True)
        if not commit_output or "nothing to commit" in commit_output:
            click.echo(Fore.YELLOW + "[AVISO] O Git não encontrou nenhuma alteração para commitar."); return

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")