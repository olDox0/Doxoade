# doxoade/commands/save.py
import sys
import subprocess
import re

import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _load_config,
    _run_git_command
)

__version__ = "34.0 Alfa"

@click.command('save')
@click.pass_context
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo que o 'check' encontre avisos ou apenas o erro de ambiente.")
def save(ctx, message, force):
    """Executa um 'commit seguro', protegendo seu repositório de código com erros."""
    arguments = ctx.params
    path = '.'
    
    with ExecutionLogger('save', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")
        click.echo(Fore.YELLOW + "\nPasso 1: Executando 'doxoade check' para garantir a qualidade do código...")

        config = _load_config()
        ignore_list = config.get('ignore', [])
        
        # Usamos o runner explícito para garantir a execução no ambiente correto
        runner_path = 'doxoade.bat' # ou o nome do seu runner
        check_command = [runner_path, 'check', '.']
        for folder in ignore_list:
            check_command.extend(['--ignore', folder])

        check_result = subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace')

        output = check_result.stdout
        return_code = check_result.returncode
        has_warnings = "Aviso(s)" in output and "0 Aviso(s)" not in output
        is_env_error_present = "Ambiente Inconsistente" in output
        
        num_errors = int(re.search(r'(\d+) Erro\(s\)', output).group(1)) if re.search(r'(\d+) Erro\(s\)', output) else 0
        num_non_env_errors = num_errors - 1 if is_env_error_present else num_errors

        if return_code != 0:
            if force and num_non_env_errors == 0:
                click.echo(Fore.YELLOW + "\n[AVISO] Erro de ambiente ignorado devido ao uso da flag --force.")
            else:
                logger.add_finding('error', "'doxoade check' encontrou erros críticos. Salvamento abortado.", details=output)
                click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros críticos. O salvamento foi abortado.")
                safe_output = output.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
                print(safe_output)
                sys.exit(1)
        
        if has_warnings and not force:
            if not click.confirm(Fore.YELLOW + "\n[AVISO] 'doxoade check' encontrou avisos. Deseja continuar com o salvamento mesmo assim?"):
                click.echo("Salvamento abortado pelo usuário.")
                sys.exit(0)
        
        click.echo(Fore.GREEN + "[OK] Verificação de qualidade concluída.")
        
        click.echo(Fore.YELLOW + "\nPasso 2: Verificando se há alterações para salvar...")
        status_output = _run_git_command(['status', '--porcelain'], capture_output=True)
        if status_output is None: sys.exit(1)
            
        if not status_output:
            click.echo(Fore.GREEN + "[OK] Nenhuma alteração nova para salvar. A árvore de trabalho está limpa.")
            return

        click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
        if not _run_git_command(['commit', '-a', '-m', message]):
            click.echo(Fore.YELLOW + "Tentativa inicial de commit falhou (pode haver arquivos novos). Tentando com 'git add .'...")
            if not _run_git_command(['add', '.']): sys.exit(1)
            if not _run_git_command(['commit', '-m', message]): sys.exit(1)
            
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso no repositório!")