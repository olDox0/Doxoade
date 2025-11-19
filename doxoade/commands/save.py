# doxoade/commands/save.py
import sys
import os
#import json
#import subprocess
from datetime import datetime, timezone
import click
from colorama import Fore, Style
import tempfile # Import que faltava

from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _run_git_command, _present_results
from .check import run_check_logic # Importa a lógica de análise

def _run_check_on_content(content):
    """Executa a lógica do check em um conteúdo de string usando um arquivo temporário."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.py', encoding='utf-8') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    # Executa a análise no arquivo temporário
    # Usamos flags para acelerar, pois só nos importam os hashes dos findings
    results = run_check_logic(path=os.path.dirname(tmp_path), cmd_line_ignore=[], fix=False, debug=False, fast=True, no_imports=True)
    
    os.remove(tmp_path) # Limpa o arquivo temporário
    return results.get('findings', [])


def _manage_incidents_and_learn(logger, project_path):
    """(Versão Final e Robusta) Aprende com as mudanças comparando o estado atual com o do último commit."""
    click.echo(Fore.CYAN + "\n--- [LEARN] Verificando se as mudanças resolveram problemas... ---")
    
    # 1. Pega os arquivos Python modificados que estão no "staging area"
    changed_files_str = _run_git_command(['diff', '--staged', '--name-only', '--diff-filter=M', '*.py'], capture_output=True)
    if not changed_files_str:
        click.echo(Fore.WHITE + "   > Nenhuma modificação em arquivos Python preparada para commit.")
        return

    # 2. Executa a análise de qualidade APENAS UMA VEZ no estado ATUAL (pós-correção)
    current_results = run_check_logic('.', [], False, False, no_cache=True)
    current_findings_map = {f['hash']: f for f in current_results.get('findings', [])}
    
    learned_count = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for file_path in changed_files_str.splitlines():
            # 3. Pega a versão do arquivo no último commit (o estado "antes")
            old_content = _run_git_command(['show', f'HEAD:{file_path}'], capture_output=True, silent_fail=True)
            if old_content is None: continue # É um arquivo novo, não havia problemas antes

            # 4. Analisa o conteúdo antigo para saber quais problemas existiam
            old_findings_in_file = _run_check_on_content(old_content)
            old_hashes = {f['hash'] for f in old_findings_in_file}
            
            # 5. Compara: quais problemas do estado antigo não existem mais no estado atual?
            for f_hash in old_hashes:
                if f_hash not in current_findings_map: # Problema resolvido!
                    diff_output = _run_git_command(['diff', 'HEAD', '--', file_path], capture_output=True)
                    if diff_output:
                        # Precisamos da mensagem do erro original
                        original_finding = next((f for f in old_findings_in_file if f['hash'] == f_hash), None)
                        message = original_finding.get('message', 'Mensagem desconhecida') if original_finding else 'Mensagem desconhecida'

                        cursor.execute(
                            "INSERT OR REPLACE INTO solutions (finding_hash, resolution_diff, commit_hash, project_path, timestamp, file_path, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (f_hash, diff_output, "PENDING_COMMIT", project_path, datetime.now(timezone.utc).isoformat(), file_path, message)
                        )
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

        # PASSO 1: Preparar TODAS as mudanças primeiro.
        click.echo(Fore.YELLOW + "\nPasso 1: Preparando todos os arquivos para o commit (git add .)...")
        _run_git_command(['add', '.'])
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")
        
        # PASSO 2: Aprender com as mudanças que acabamos de preparar.
        _manage_incidents_and_learn(logger, project_path)

        # PASSO 3: Verificar a qualidade do estado FINAL.
        click.echo(Fore.YELLOW + "\nPasso 3: Verificando a qualidade final do código...")
        final_check_results = run_check_logic('.', [], False, False, no_cache=True)
        
        summary = final_check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros. Commit abortado.")
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
        
        # Atualiza as soluções com o hash do commit real
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        if new_commit_hash:
            conn = get_db_connection()
            try:
                conn.execute("UPDATE solutions SET commit_hash = ? WHERE commit_hash = 'PENDING_COMMIT'", (new_commit_hash,))
                conn.commit()
            finally:
                conn.close()

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")