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
    _present_results # <-- Import adicionado
)

def _run_quality_check(logger):
    """Executa o 'doxoade check' e retorna o resultado completo."""
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

def _learn_from_fixes(old_incident, current_results, logger):
    """Compara um incidente antigo com os resultados atuais para aprender as soluções."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Analisando correções... ---")

    # NOVA VERIFICAÇÃO: Garante que estamos comparando estados diferentes
    current_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
    if old_incident.get('commit_hash') == current_commit_hash and not _run_git_command(['diff', '--staged'], capture_output=True):
        click.echo(Fore.WHITE + "Nenhuma mudança de código detectada desde o último incidente. Pulando aprendizado.")
        return

    old_findings = {f['hash']: f for f in old_incident.get('findings', [])}
    current_hashes = {f['hash'] for f in current_results.get('findings', [])}
    
    resolved_hashes = set(old_findings.keys()) - current_hashes
    
    if not resolved_hashes:
        click.echo(Fore.WHITE + "Nenhum problema previamente identificado foi resolvido neste commit.")
        return

    diff_output = _run_git_command(['diff', '--staged'], capture_output=True)
    if not diff_output:
        click.echo(Fore.YELLOW + "   > As correções não foram adicionadas ao 'staging area' do Git. Impossível aprender.")
        return

    # O resto da função permanece exatamente o mesmo...
    conn = get_db_connection()
    cursor = conn.cursor()
    learned_count = 0
    
    try:
        for f_hash in resolved_hashes:
            resolved_finding = old_findings[f_hash]
            
            cursor.execute("""
                INSERT OR REPLACE INTO solutions 
                (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                f_hash,
                diff_output,
                "PENDING_COMMIT",
                os.getcwd(),
                datetime.now(timezone.utc).isoformat(),
                resolved_finding.get('file', 'N/A')
            ))
            learned_count += 1
        
        conn.commit()
        click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s) no banco de dados.")
        logger.add_finding("INFO", f"{learned_count} soluções aprendidas.", category="LEARNING")
    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao salvar soluções no banco de dados.", details=str(e))
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
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        # PASSO 1: Preparar arquivos
        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        if not _run_git_command(['add', '.']):
            click.echo(Fore.RED + "[ERRO] Falha ao preparar os arquivos."); sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")

        # PASSO 2: Executar verificação de qualidade
        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade ('doxoade check')...")
        check_results, error_msg = _run_quality_check(logger)
        if check_results is None: # Verificação alterada para 'is None' para mais robustez
            click.echo(Fore.RED + f"[ERRO] {error_msg}"); sys.exit(1)
        
        # --- INÍCIO DA CORREÇÃO LÓGICA ---
        
        # PASSO 3: Lógica de Aprendizagem (SEMPRE tenta aprender se um incidente existe)
        incident_file = os.path.join('.doxoade_cache', 'incidents.json')
        if os.path.exists(incident_file):
            try:
                with open(incident_file, 'r', encoding='utf-8') as f:
                    incident_data = json.load(f)
                
                # A chamada de aprendizado agora acontece aqui, incondicionalmente
                _learn_from_fixes(incident_data, check_results, logger)
                
                # Limpa o incidente somente após a tentativa de aprendizado
                os.remove(incident_file)
            except (IOError, json.JSONDecodeError):
                pass # Ignora se não conseguir ler ou deletar o arquivo de incidente

        # PASSO 4: Decidir sobre o commit com base nos resultados do check
        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            logger.add_finding('ERROR', "Commit abortado devido a erros do 'check'.", details=json.dumps(check_results))
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            _present_results('text', check_results)
            sys.exit(1)
        elif has_errors and force:
            click.echo(Fore.YELLOW + "\n[AVISO] Erros encontrados, mas o commit foi forçado.")
            logger.add_finding('WARNING', "Commit forçado apesar dos erros do 'check'.")
        else:
             click.echo(Fore.GREEN + "\n[OK] Verificação de qualidade concluída sem erros críticos.")

        # --- FIM DA CORREÇÃO LÓGICA ---
        
        # PASSO 5: Executar o commit
        click.echo(Fore.YELLOW + f"\nPasso 5: Criando commit com a mensagem: '{message}'...")
        if not _run_git_command(['commit', '-m', message]):
            click.echo(Fore.YELLOW + "[AVISO] O Git não encontrou nenhuma alteração para commitar.")
            return
            
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")