# doxoade/commands/canonize.py
import os
import sys
import json
import click
import subprocess
from colorama import Fore, Style
from ..shared_tools import _sanitize_json_output, _get_git_commit_hash, CANON_DIR

@click.command('canonize')
@click.option('--all', 'all_project', is_flag=True, help="Canoniza o estado do projeto atual.")
def canonize(all_project):
    """Executa o 'check' no projeto inteiro e salva a saída JSON como 'cânone'."""
    if not all_project:
        click.echo(Fore.YELLOW + "Comando 'canonize' agora requer a flag '--all'. O modo de fixtures foi descontinuado.")
        return

    os.makedirs(CANON_DIR, exist_ok=True)
    git_hash = _get_git_commit_hash('.')
    doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')

    click.echo(Fore.CYAN + "--- [CANONIZE --ALL] Criando snapshot do projeto atual ---")
    click.echo(Fore.CYAN + f"  > Usando o estado do commit Git: {git_hash[:7]}")

    command_parts = [doxoade_executable, 'check', '.', '--format=json']
    result = subprocess.run(command_parts, capture_output=True, text=True, shell=False, encoding='utf-8', errors='replace')
    
    try:
        results_json = json.loads(result.stdout)
    except json.JSONDecodeError:
        click.echo(Fore.RED + Style.BRIGHT + "Erro: A saída do 'check' não foi um JSON válido e não pode ser canonizada.")
        click.echo(Style.DIM + f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}")
        sys.exit(1)

    sanitized_json = _sanitize_json_output(results_json, '.')
    snapshot_data = {'git_hash': git_hash, 'report': sanitized_json}
    snapshot_path = os.path.join(CANON_DIR, "project_snapshot.json")
    
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
    
    click.echo(Fore.GREEN + f"    [OK] Snapshot do projeto '{snapshot_path}' criado/atualizado.")
    click.echo(Fore.CYAN + "\n--- Concluído ---")