# doxoade/commands/regression_test.py
import os
import sys
import toml
import json
import click
from colorama import Fore, Style
import jsondiff
from .check import run_check_logic
#from ..shared_tools import _sanitize_json_output, REGRESSION_BASE_DIR, FIXTURES_DIR, CANON_DIR, CONFIG_FILE
from ..shared_tools import _sanitize_json_output, CANON_DIR, CONFIG_FILE, FIXTURES_DIR
@click.command('regression-test')
def regression_test():
    """Compara a saída JSON atual dos comandos com os snapshots canônicos."""
    click.echo(Fore.CYAN + "--- [REGRESSION-TEST] Iniciando a verificação de regressões (modo JSON) ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    failures = 0

    for case in test_cases:
        case_id = case.get('id')
        project_name = case.get('project')
        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        
        click.echo(Fore.WHITE + f"  > Verificando teste '{case_id}'...")

        # Chama a lógica do check diretamente
        current_results = run_check_logic(path=project_path, cmd_line_ignore=[], fix=False, debug=False)
        sanitized_current = _sanitize_json_output(current_results, project_path)

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.json")
        if not os.path.exists(snapshot_path):
            click.echo(Fore.YELLOW + f"    [AVISO] Snapshot canônico '{snapshot_path}' não encontrado.")
            continue

        with open(snapshot_path, 'r', encoding='utf-8') as f:
            sanitized_canonical = json.load(f)

        diff = jsondiff.diff(sanitized_canonical, sanitized_current)

        if not diff:
            click.echo(Fore.GREEN + f"    [OK] Teste '{case_id}' passou.")
        else:
            failures += 1
            click.echo(Fore.RED + Style.BRIGHT + f"    [FALHA] Regressão detectada em '{case_id}'!")
            click.echo(Style.DIM + "--- DIFERENÇAS DETECTADAS (Canônico -> Atual) ---")
            click.echo(Style.DIM + json.dumps(diff, indent=2))
            
    click.echo(Fore.CYAN + "\n--- Concluído ---")
    if failures > 0:
        click.echo(Fore.RED + f"{failures} teste(s) de regressão falharam.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "Todos os testes de regressão passaram com sucesso.")