# doxoade/commands/diff.py
import os
import sys
import subprocess
import click
import re
from colorama import Fore, Style

from ..shared_tools import _run_git_command

def _present_diff_output(output):
    """(Versão Polida) Analisa a saída do 'git diff' e a formata de forma elegante."""
    old_line_num = 0
    new_line_num = 0

    for line in output.splitlines():
        if line.startswith('@@'):
            match = re.search(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if match:
                old_line_num = int(match.group(1))
                new_line_num = int(match.group(2))
                click.echo(Fore.CYAN + f"\n\n--- Mudança(s) a partir da linha {old_line_num} ---")
            else:
                click.echo(Fore.CYAN + line)
            continue

        if line.startswith('diff --git') or line.startswith('index') or line.startswith('---') or line.startswith('+++'):
            continue

        if not line: continue

        char = line[0]
        content = line[1:]
        
        if char == '+':
            click.echo(Fore.GREEN + f"     | {new_line_num:4d} | +    {content}")
            new_line_num += 1
        elif char == '-':
            click.echo(Fore.RED   + f"{old_line_num:4d} |      | -    {content}")
            old_line_num += 1
        else: # Linha de contexto
            # --- A CORREÇÃO ESTÁ AQUI ---
            # Mudamos de Style.DIM para Fore.WHITE para maior contraste.
            click.echo(Fore.WHITE + f"{old_line_num:4d} | {new_line_num:4d} |      {content}")
            old_line_num += 1
            new_line_num += 1

@click.command('diff')
@click.argument('path', type=click.Path(exists=True), default='.')
def diff(path):
    """
    Mostra as mudanças entre a versão de trabalho atual e o último commit (git diff).
    """
    git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True, silent_fail=True)
    if not git_root:
        click.echo(Fore.RED + "Erro: Este não parece ser um repositório Git.")
        sys.exit(1)

    relative_path = os.path.relpath(os.path.abspath(path), git_root)

    status_output = _run_git_command(['status', '--porcelain', relative_path], capture_output=True)
    if status_output and status_output.startswith('??'):
        click.echo(Fore.CYAN + f"O arquivo '{relative_path}' é novo e ainda não foi rastreado pelo Git.")
        return

    command = ['git', 'diff', 'HEAD', '--', relative_path]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')

    if result.stderr:
        click.echo(Fore.RED + f"Erro ao executar o git diff: {result.stderr}")
        sys.exit(1)

    if not result.stdout:
        click.echo(Fore.GREEN + f"[OK] Nenhuma mudança detectada em '{relative_path}' desde o último commit.")
    else:
        click.echo(Fore.CYAN + f"--- Diferenças em '{relative_path}' desde o último commit ---")
        _present_diff_output(result.stdout)