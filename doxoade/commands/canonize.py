#doxoade/commands/canonize.py
import os
import sys
import toml
import json
import click
from colorama import Fore
from .check import run_check_logic
#from ..shared_tools import _sanitize_json_output, REGRESSION_BASE_DIR, FIXTURES_DIR, CANON_DIR, CONFIG_FILE
from ..shared_tools import _sanitize_json_output, CANON_DIR, CONFIG_FILE, FIXTURES_DIR
@click.command('canonize')
def canonize():
    """Executa os casos de teste e salva a saída JSON como 'cânone'."""
    click.echo(Fore.CYAN + "--- [CANONIZE] Iniciando a criação de snapshots JSON de regressão ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    os.makedirs(CANON_DIR, exist_ok=True)
    
    for case in test_cases:
        case_id = case.get('id')
        project_name = case.get('project')
        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        
        click.echo(Fore.WHITE + f"  > Executando teste '{case_id}' para canonização...")

        results = run_check_logic(path=project_path, cmd_line_ignore=[], fix=False, debug=False)
        
        sanitized_json = _sanitize_json_output(results, project_path)

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.json")
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(sanitized_json, f, indent=2, ensure_ascii=False)
        
        click.echo(Fore.GREEN + f"    [OK] Snapshot '{snapshot_path}' criado/atualizado.")

    click.echo(Fore.CYAN + "\n--- Concluído ---")