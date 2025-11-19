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
from ..shared_tools import ExecutionLogger, _run_git_command, _present_results

def _run_quality_check():
    """Executa 'doxoade check' e retorna os resultados como um dicionário."""
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path: return None, "Runner 'doxoade' não encontrado."
    
    cmd = [runner_path, 'check', '.', '--format', 'json']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"A análise de qualidade falhou.\n{result.stderr}"

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

def _manage_incidents_and_learn(current_results, logger, project_path):
    """Gerencia o ciclo de vida de incidentes: aprende com os resolvidos e atualiza os abertos."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes e aprendendo com correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Pega os incidentes antigos
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = cursor.fetchall()
        
        current_findings = current_results.get('findings', [])
        current_hashes = {f['hash'] for f in current_findings}
        
        learned_count = 0
        if open_incidents:
            old_hashes = {inc['finding_hash']: inc for inc in open_incidents}
            resolved_hashes = set(old_hashes.keys()) - current_hashes
            
            if resolved_hashes:
                click.echo(Fore.WHITE + f"   > {len(resolved_hashes)} problema(s) resolvido(s) detectado(s).")
                for f_hash in resolved_hashes:
                    incident = old_hashes[f_hash]
                    file_path = incident['file_path']
                    diff_output = _run_git_command(['diff', '--staged', '--', file_path], capture_output=True)
                    if not diff_output: continue

                    cursor.execute(
                        "INSERT OR REPLACE INTO solutions (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path) VALUES (?, ?, ?, ?, ?, ?)",
                        (f_hash, diff_output, "PENDING_COMMIT", project_path, datetime.now(timezone.utc).isoformat(), file_path)
                    )
                    learned_count += 1
        
        # ATUALIZAÇÃO: Limpa os incidentes antigos e registra os novos
        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
        if current_findings:
            commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True) or "N/A"
            incidents_to_add = [
                (f.get('hash'), f.get('file'), commit_hash, datetime.now(timezone.utc).isoformat(), project_path)
                for f in current_findings if f.get('hash')
            ]
            if incidents_to_add:
                cursor.executemany("INSERT OR REPLACE INTO open_incidents VALUES (?, ?, ?, ?, ?)", incidents_to_add)

        conn.commit()

        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhum incidente resolvido para aprender neste commit.")

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

        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        if not _run_git_command(['add', '.']): sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")

        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade ('doxoade check')...")
        check_results, error_msg = _run_quality_check() # Não precisa mais passar o logger
        if check_results is None:
            click.echo(Fore.RED + f"[ERRO] {error_msg}"); sys.exit(1)
        
        _manage_incidents_and_learn(check_results, logger, project_path)

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