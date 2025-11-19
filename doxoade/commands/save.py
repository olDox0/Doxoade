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
from .check import run_check_logic

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
    """(Versão Flexível) Aprende com incidentes resolvidos comparando com o commit do incidente."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando incidentes e aprendendo com correções... ---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        open_incidents = cursor.fetchall()
        if not open_incidents:
            click.echo(Fore.WHITE + "   > Nenhum incidente aberto conhecido para este projeto.")
            return

        current_hashes = {f['hash'] for f in current_results.get('findings', [])}
        learned_count = 0
        
        for incident in open_incidents:
            finding_hash = incident['finding_hash']
            if finding_hash not in current_hashes:
                # O problema foi resolvido!
                file_path = incident['file_path']
                incident_commit = incident['commit_hash']

                # NOVA LÓGICA: Compara o estado ATUAL do arquivo com o estado do commit ONDE o erro foi encontrado.
                diff_output = _run_git_command(['diff', incident_commit, 'HEAD', '--', file_path], capture_output=True)
                
                if not diff_output: continue

                cursor.execute(
                    "INSERT OR REPLACE INTO solutions (...) VALUES (?, ?, ?, ?, ?, ?)",
                    (finding_hash, diff_output, "PENDING_COMMIT", project_path, datetime.now(timezone.utc).isoformat(), file_path)
                )
                cursor.execute("DELETE FROM open_incidents WHERE finding_hash = ?", (finding_hash,))
                learned_count += 1
        
        conn.commit()
        if learned_count > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s) e armazenada(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhum incidente conhecido foi resolvido com as mudanças atuais.")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao gerenciar incidentes.", details=str(e))
    finally:
        conn.close()

def _get_findings_from_content(content, file_path, logger):
    """Executa a lógica de análise em um conteúdo de arquivo em memória."""
    # Esta é uma simulação simplificada. Idealmente, a lógica do `check`
    # seria refatorada para aceitar conteúdo de string diretamente.
    # Por enquanto, vamos usar um arquivo temporário.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    results = run_check_logic(os.path.dirname(tmp_path), [], False, False)
    os.remove(tmp_path)
    return results.get('findings', [])

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
        
        # 1. Pega os arquivos modificados
        changed_files_str = _run_git_command(['diff', '--staged', '--name-only', '--diff-filter=M'], capture_output=True)
        if not changed_files_str:
            if not _run_git_command(['commit', '-m', message]):
                 click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return
            click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!"); return

        changed_files = changed_files_str.splitlines()
        
        # 2. Roda o check no estado ATUAL
        current_results = run_check_logic('.', [], False, False)
        current_findings = current_results.get('findings', [])
        
        # 3. APRENDIZADO
        click.echo(Fore.CYAN + "\n--- [LEARN] Verificando se as mudanças resolveram problemas... ---")
        learned_count = 0
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for file_path in changed_files:
            # Pega a versão do arquivo no último commit
            old_content = _run_git_command(['show', f'HEAD:{file_path}'], capture_output=True, silent_fail=True)
            if old_content is None: continue # Arquivo novo, não havia problemas antes
            
            old_findings_in_file = _get_findings_from_content(old_content, file_path, logger)
            current_findings_in_file = [f for f in current_findings if os.path.normcase(f.get('file', '')) == os.path.normcase(file_path)]
            
            old_hashes = {f['hash'] for f in old_findings_in_file}
            current_hashes = {f['hash'] for f in current_findings_in_file}
            resolved_hashes = old_hashes - current_hashes

            if resolved_hashes:
                diff_output = _run_git_command(['diff', '--staged', '--', file_path], capture_output=True)
                for f_hash in resolved_hashes:
                    cursor.execute("INSERT OR REPLACE INTO solutions VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                                   (f_hash, diff_output, "PENDING", project_path, datetime.now(timezone.utc).isoformat(), file_path))
                    learned_count += 1
        
        if learned_count > 0:
            conn.commit()
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhuma solução aprendida neste commit.")
        conn.close()

        # 4. DECISÃO DE COMMIT
        has_errors = current_results.get('summary', {}).get('critical', 0) > 0 or current_results.get('summary', {}).get('errors', 0) > 0
        if has_errors and not force:
            _present_results('text', current_results)
            _run_git_command(['reset'])
            sys.exit(1)

        # 5. COMMIT
        if not _run_git_command(['commit', '-m', message]):
            click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")