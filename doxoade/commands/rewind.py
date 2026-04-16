# doxoade/doxoade/commands/rewind.py
import click
import shutil
import os
import sys
import subprocess
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command

@click.command('rewind')
@click.argument('file_path', required=False, type=click.Path(exists=False))
@click.option('--commit', '-c', help='Hash do commit alvo para onde voltar.')
@click.option('--list', '-l', 'show_list', is_flag=True, help='Lista o histórico de commits (do arquivo ou global).')
def rewind(file_path, commit, show_list):
    """
    Reverte um arquivo para uma versão anterior (Time Travel).
    
    Cria um backup automático da versão atual antes de reverter.
    
    Exemplos:
      doxoade rewind --list                (Ver histórico do projeto)
      doxoade rewind arquivo.py --list     (Ver histórico do arquivo)
      doxoade rewind arquivo.py -c a1b2c3  (Voltar arquivo para o commit a1b2c3)
    """
    if show_list:
        cmd = ['log', '--oneline', '--graph', '--decorate', '-n', '20']
        if file_path:
            click.echo(Fore.CYAN + f'--- Histórico de alterações para: {file_path} ---')
            cmd.extend(['--', file_path])
        else:
            click.echo(Fore.CYAN + '--- Histórico Recente do Projeto ---')
        try:
            subprocess.run(['git'] + cmd, check=True)
        except subprocess.CalledProcessError:
            click.echo(Fore.RED + '[ERRO] Falha ao ler histórico do Git.')
        return
    if not file_path:
        click.echo(Fore.RED + '[ERRO] Você precisa especificar um arquivo para rebobinar.')
        click.echo('Uso: doxoade rewind <arquivo> -c <hash>')
        sys.exit(1)
    if not commit:
        click.echo(Fore.RED + '[ERRO] Você precisa especificar o hash do commit alvo (-c).')
        click.echo(f"Dica: Use 'doxoade rewind {file_path} --list' para ver os hashes.")
        sys.exit(1)
    if not os.path.exists(file_path):
        click.echo(Fore.YELLOW + f"[AVISO] O arquivo '{file_path}' não existe atualmente no disco.")
        if not click.confirm('Deseja tentar recuperá-lo do histórico mesmo assim?'):
            sys.exit(0)
    click.echo(Fore.CYAN + f"--- [REWIND] Iniciando reversão de '{file_path}' ---")
    if os.path.exists(file_path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'{file_path}.{timestamp}.bak'
        try:
            shutil.copy2(file_path, backup_path)
            click.echo(Fore.GREEN + f'[BKP] Backup de segurança criado: {backup_path}')
        except IOError as e:
            click.echo(Fore.RED + f'[ERRO FATAL] Falha ao criar backup: {e}')
            click.echo('Operação abortada para proteger seus dados.')
            sys.exit(1)
    else:
        click.echo(Fore.WHITE + '   > Arquivo atual não existe, pulando backup.')
    click.echo(Fore.YELLOW + f'   > Revertendo para o commit {commit}...')
    try:
        if not _run_git_command(['cat-file', '-t', commit], silent_fail=True):
            click.echo(Fore.RED + f"[ERRO] O commit '{commit}' não foi encontrado.")
            sys.exit(1)
        result = subprocess.run(['git', 'checkout', commit, '--', file_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            click.echo(Fore.GREEN + Style.BRIGHT + '[SUCESSO] Arquivo revertido com sucesso.')
            click.echo(Fore.WHITE + '   > O arquivo no disco agora é a versão antiga.')
            click.echo(Fore.WHITE + '   > Para desfazer, delete o arquivo e renomeie o .bak criado.')
        else:
            click.echo(Fore.RED + '[ERRO] Falha no Git:')
            click.echo(result.stderr)
            if os.path.exists(backup_path) and os.path.exists(file_path):
                pass
    except Exception as e:
        click.echo(Fore.RED + f'[ERRO CRÍTICO] {e}')