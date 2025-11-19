# doxoade/commands/save.py
import sys
#import subprocess
#import shutil
import os
import json
import subprocess
from datetime import datetime, timezone
import click
from colorama import Fore, Style

from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _run_git_command, _present_results
from .check import run_check_logic # Lógica de análise importada

def _run_quality_check():
    """Executa 'doxoade check' e retorna os resultados como um dicionário."""
    # Chama o módulo doxoade diretamente com o interpretador atual
    cmd = [sys.executable, '-m', 'doxoade', 'check', '.', '--format', 'json']
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, f"A análise de qualidade falhou.\n{result.stderr}"

def _learn_from_fixes(logger, project_path):
    """Aprende com as mudanças preparadas (staged), comparando-as com o estado do último commit (HEAD)."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando se as mudanças resolveram problemas... ---")

    # Pega apenas os arquivos Python modificados que estão no staging area
    changed_files_str = _run_git_command(['diff', '--staged', '--name-only', '--diff-filter=M', '*.py'], capture_output=True)
    if not changed_files_str:
        click.echo(Fore.WHITE + "   > Nenhuma modificação em arquivos Python preparada para commit.")
        return

    # Executa a análise de qualidade APENAS UMA VEZ no estado atual (pós-correção)
    current_results = run_check_logic('.', [], False, False)
    current_findings_map = {f['hash']: f for f in current_results.get('findings', [])}

    learned_count = 0
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for file_path in changed_files_str.splitlines():
            # Pega o conteúdo do arquivo no último commit
            old_content = _run_git_command(['show', f'HEAD:{file_path}'], capture_output=True, silent_fail=True)
            if old_content is None: continue # Arquivo novo

            # Analisa o conteúdo antigo em memória (usando um truque com arquivo temporário)
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tmp:
                tmp.write(old_content)
                tmp_path = tmp.name
            
            old_results = run_check_logic(os.path.dirname(tmp_path), [], False, False, fast=True, no_imports=True)
            os.remove(tmp_path)
            
            old_hashes = {f['hash'] for f in old_results.get('findings', [])}
            
            # Compara os problemas do arquivo antigo com os problemas globais atuais
            for f_hash in old_hashes:
                if f_hash not in current_findings_map: # Problema resolvido!
                    diff_output = _run_git_command(['diff', '--staged', '--', file_path], capture_output=True)
                    if diff_output:
                        cursor.execute("INSERT OR REPLACE INTO solutions VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                                       (f_hash, diff_output, "PENDING", project_path, datetime.now(timezone.utc).isoformat(), file_path))
                        learned_count += 1
        
        if learned_count > 0:
            conn.commit()
            click.echo(Fore.GREEN + f"[OK] {learned_count} solução(ões) aprendida(s).")
        else:
            click.echo(Fore.WHITE + "   > Nenhuma solução aprendida neste commit.")
    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao aprender com as correções.", details=str(e))
    finally:
        conn.close()

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

        # PASSO 1: Preparar TODAS as mudanças primeiro. Esta é a correção crucial.
        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        if not _run_git_command(['add', '.']): 
            click.echo(Fore.RED + "[ERRO] Falha ao preparar os arquivos."); sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")
        
        # PASSO 2: Aprender com as mudanças que acabamos de preparar.
        _learn_from_fixes(logger, project_path)

        # PASSO 3: Verificar a qualidade do estado FINAL.
        click.echo(Fore.YELLOW + "\nPasso 3: Verificando a qualidade final do código...")
        final_check_results = run_check_logic('.', [], False, False, no_cache=True) # Força reanálise
        
        summary = final_check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros no estado final. Commit abortado.")
            _present_results('text', final_check_results)
            click.echo(Fore.YELLOW + "Desfazendo 'git add' para permitir a correção...")
            _run_git_command(['reset'])
            sys.exit(1)
        
        if has_errors and force:
            click.echo(Fore.YELLOW + "\n[AVISO] Erros encontrados, mas o commit foi forçado.")

        # PASSO 4: Fazer o commit.
        click.echo(Fore.YELLOW + f"\nPasso 4: Criando commit com a mensagem: '{message}'...")
        commit_output = _run_git_command(['commit', '-m', message], capture_output=True)
        if "nothing to commit" in (commit_output or ""):
            click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar."); return
        
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")