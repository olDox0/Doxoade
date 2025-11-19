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
    """Executa 'doxoade check' no formato JSON e retorna os resultados."""
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path:
        return None, "Runner 'doxoade' não encontrado no PATH."
    
    check_command = [runner_path, 'check', '.', '--format', 'json']
    result = subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"A análise de qualidade falhou ou produziu uma saída inválida.\n{result.stderr}"

def _learn_from_fixes(old_incident, current_results, logger, project_path):
    """
    (Versão Final) Compara um incidente antigo (do incidents.json) com os 
    resultados atuais para aprender e salvar as soluções no banco de dados.
    """
    click.echo(Fore.CYAN + "\n--- [LEARN] Analisando correções... ---")
    
    # 1. Mapeia os 'findings' antigos e atuais para fácil consulta por hash
    old_findings_map = {f['hash']: f for f in old_incident.get('findings', [])}
    current_hashes = {f['hash'] for f in current_results.get('findings', [])}
    
    # 2. Identifica os hashes dos problemas que foram resolvidos
    resolved_hashes = set(old_findings_map.keys()) - current_hashes
    
    if not resolved_hashes:
        click.echo(Fore.WHITE + "   > Nenhum problema previamente identificado foi resolvido neste commit.")
        return

    # 3. Conecta ao banco de dados para salvar o aprendizado
    conn = get_db_connection()
    cursor = conn.cursor()
    learned_count = 0
    
    try:
        for f_hash in resolved_hashes:
            # Pega os detalhes completos do problema original que foi resolvido
            resolved_finding = old_findings_map[f_hash]
            file_path = resolved_finding.get('file')
            
            # Se não houver um arquivo associado, não podemos gerar um diff.
            if not file_path:
                continue

            # 4. Captura o 'diff' APENAS para o arquivo onde o problema foi resolvido.
            #    Isso torna a solução granular e precisa.
            diff_output = _run_git_command(['diff', '--staged', '--', file_path], capture_output=True)
            
            # Se não houver 'diff' para este arquivo, pula para o próximo.
            if not diff_output:
                continue

            # 5. Salva a solução completa no banco de dados, incluindo a mensagem do erro.
            cursor.execute("""
                INSERT OR REPLACE INTO solutions 
                (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f_hash,
                diff_output,
                "PENDING_COMMIT",  # O hash real será atualizado após o commit
                project_path,
                datetime.now(timezone.utc).isoformat(),
                file_path,
                resolved_finding.get('message', 'Mensagem de erro não registrada') # Salva a mensagem
            ))
            learned_count += 1
        
        conn.commit()
        
        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Embora problemas tenham sido resolvidos, as mudanças não estavam preparadas (staged) para aprendizado.")

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
        project_path = os.getcwd()
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        # PASSO 1: Preparar arquivos
        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        if not _run_git_command(['add', '.']): 
            click.echo(Fore.RED + "[ERRO] Falha ao preparar os arquivos."); sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")
        
        # PASSO 2: Executar verificação de qualidade
        click.echo(Fore.YELLOW + "\nPasso 2: Executando verificação de qualidade ('doxoade check')...")
        check_results, error_msg = _run_quality_check()
        if check_results is None:
            click.echo(Fore.RED + f"[ERRO] {error_msg}"); sys.exit(1)
        
        # PASSO 3: Lógica de Aprendizagem
        incident_file = os.path.join('.doxoade_cache', 'incidents.json')
        if os.path.exists(incident_file):
            try:
                with open(incident_file, 'r', encoding='utf-8') as f:
                    incident_data = json.load(f)
                _learn_from_fixes(incident_data, check_results, logger, project_path)
                # Limpa o incidente somente após a tentativa de aprendizado
                os.remove(incident_file) 
            except (IOError, json.JSONDecodeError):
                pass

        # PASSO 4: Decidir sobre o commit
        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            logger.add_finding('ERROR', "Commit abortado devido a erros do 'check'.", details=json.dumps(check_results))
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
            _present_results('text', check_results)
            click.echo(Fore.YELLOW + "Desfazendo 'git add' para permitir a correção...")
            _run_git_command(['reset'])
            sys.exit(1)
        
        if has_errors and force:
            click.echo(Fore.YELLOW + "\n[AVISO] Erros encontrados, mas o commit foi forçado.")
        else:
            click.echo(Fore.GREEN + "\n[OK] Verificação de qualidade concluída sem erros críticos.")

        # PASSO 5: Executar o commit e atualizar soluções
        click.echo(Fore.YELLOW + f"\nPasso 5: Criando commit com a mensagem: '{message}'...")
        commit_output = _run_git_command(['commit', '-m', message], capture_output=True)
        if "nothing to commit" in (commit_output or ""):
            click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return
        
        # Pega o hash do commit que acabamos de criar
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        if new_commit_hash:
            conn = get_db_connection()
            try:
                # Atualiza as soluções pendentes com o hash do commit real
                conn.execute("UPDATE solutions SET commit_hash = ? WHERE commit_hash = 'PENDING_COMMIT'", (new_commit_hash,))
                conn.commit()
            finally:
                conn.close()

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")