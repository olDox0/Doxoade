# doxoade/commands/save.py
import sys
import subprocess
#import re
import shutil

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _load_config, _run_git_command

__version__ = "35.6 Alfa (Phoenix)"

def _run_quality_check(logger):
    click.echo(Fore.YELLOW + "\nPasso 1: Executando 'doxoade check'...")
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path:
        logger.add_finding('error', "Runner 'doxoade.bat' não encontrado.")
        return None, "Runner 'doxoade.bat' não encontrado no PATH."

    config = _load_config()
    ignore_list = config.get('ignore', [])
    
    check_command = [runner_path, 'check', '.']
    # Corrigido para adicionar múltiplos argumentos de ignore corretamente
    for folder in ignore_list:
        check_command.extend(['--ignore', folder])
    return subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace'), ""

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
@click.option('--force', is_flag=True, help="Força o commit mesmo se houver apenas um erro de ambiente.")
def save(ctx, message, force):
    """Executa um 'commit seguro', protegendo o repositório de código com erros."""
    arguments = ctx.params
    with ExecutionLogger('save', '.', arguments) as logger:
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        check_result, error_msg = _run_quality_check(logger)
        if not check_result:
            click.echo(Fore.RED + f"[ERRO] {error_msg}"); sys.exit(1)

        if not _can_proceed_with_commit(check_result, force, logger):
            sys.exit(1)
        
        # --- A LÓGICA RESTAURADA COMEÇA AQUI ---
        click.echo(Fore.YELLOW + "\nPasso 2: Verificando se há alterações para salvar...")
        status_output = _run_git_command(['status', '--porcelain'], capture_output=True)
        if status_output is None: sys.exit(1)
        if not status_output:
            click.echo(Fore.GREEN + "[OK] Nenhuma alteração nova para salvar. A árvore de trabalho está limpa.")
            return

        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
        # A lógica de 'commit -a' primeiro é mais eficiente
        if not _run_git_command(['commit', '-a', '-m', message]):
            click.echo(Fore.YELLOW + "Tentando com 'git add .' para arquivos novos...")
            if not _run_git_command(['add', '.']): sys.exit(1)
            if not _run_git_command(['commit', '-m', message]): 
                logger.add_finding('error', "Falha ao executar 'git commit' final.")
                sys.exit(1)
            
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")