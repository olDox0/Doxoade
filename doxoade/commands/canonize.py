# doxoade/commands/canonize.py
import os
import sys
import toml
import json
import click
from colorama import Fore

from .check import run_check_logic
# Importa a função de git e as constantes
from ..shared_tools import (
    _sanitize_json_output, 
    _get_git_commit_hash, 
#    REGRESSION_BASE_DIR, 
    FIXTURES_DIR, 
    CANON_DIR, 
    CONFIG_FILE
)

@click.command('canonize')
def canonize():
    """Executa os casos de teste e salva a saída JSON como 'cânone', incluindo o hash do Git."""
    click.echo(Fore.CYAN + "--- [CANONIZE] Iniciando a criação de snapshots JSON de regressão ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    os.makedirs(CANON_DIR, exist_ok=True)
    
    # --- NOVA LÓGICA: CAPTURA O HASH DO COMMIT ATUAL UMA VEZ ---
    # Usamos '.' para indicar que queremos o hash do projeto onde o doxoade está rodando
    git_hash = _get_git_commit_hash('.')
    click.echo(Fore.CYAN + f"  > Usando o estado do commit Git: {git_hash[:7]}")

    for case in test_cases:
        case_id = case.get('id')
        project_name = case.get('project')
        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        
        click.echo(Fore.WHITE + f"  > Executando teste '{case_id}' para canonização...")

        # Chama a lógica pura do check
        results = run_check_logic(path=project_path, cmd_line_ignore=[], fix=False, debug=False)
        
        sanitized_json = _sanitize_json_output(results, project_path)

        # --- NOVA LÓGICA: ADICIONA O HASH AO SNAPSHOT ---
        snapshot_data = {
            'git_hash': git_hash,
            'report': sanitized_json
        }

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.json")
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
        
        click.echo(Fore.GREEN + f"    [OK] Snapshot '{snapshot_path}' criado/atualizado.")

    click.echo(Fore.CYAN + "\n--- Concluído ---")