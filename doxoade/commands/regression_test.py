# doxoade/commands/regression_test.py
import os
import sys
import subprocess
import toml
import click
from colorama import Fore, Style

# Reutiliza as mesmas constantes do canonize
REGRESSION_BASE_DIR = "regression_tests"
FIXTURES_DIR = os.path.join(REGRESSION_BASE_DIR, "fixtures")
CANON_DIR = os.path.join(REGRESSION_BASE_DIR, "canon")
CONFIG_FILE = os.path.join(REGRESSION_BASE_DIR, "canon.toml")

def _sanitize_output(text, project_path):
    """Substitui caminhos absolutos por um placeholder para portabilidade."""
    normalized_path = os.path.normpath(project_path)
    # Garante que as barras invertidas do Windows sejam escapadas para a substituição
    escaped_path = normalized_path.replace('\\\\', '\\\\\\\\')
    return text.replace(escaped_path, "<PROJECT_PATH>")

@click.command('regression-test')
def regression_test():
    """Compara a saída atual dos comandos com os snapshots canônicos."""
    click.echo(Fore.CYAN + "--- [REGRESSION-TEST] Iniciando a verificação de regressões ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado. Execute 'setup-regression' primeiro.")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    if not test_cases:
        click.echo(Fore.YELLOW + "Nenhum caso de teste definido em 'canon.toml'.")
        return
        
    doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')
    failures = 0

    for case in test_cases:
        case_id = case.get('id')
        command = case.get('command')
        project_name = case.get('project')
        
        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        
        click.echo(Fore.WHITE + f"  > Verificando teste '{case_id}'...")

        # --- UTILITARIO 1: Gerar a Saída Atual ---
        full_command = command.replace("doxoade", f'"{doxoade_executable}"', 1)
        result = subprocess.run(
            full_command, cwd=project_path, capture_output=True, text=True, shell=True,
            encoding='utf-8', errors='replace'
        )
        
        current_output_formatted = (
            f"--- COMMAND ---\n{command}\n\n"
            f"--- EXIT CODE ---\n{result.returncode}\n\n"
            f"--- STDOUT ---\n{_sanitize_output(result.stdout, project_path)}\n\n"
            f"--- STDERR ---\n{_sanitize_output(result.stderr, project_path)}\n"
        )

        # --- UTILITARIO 2: Comparar com o Cânone ---
        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.txt")
        if not os.path.exists(snapshot_path):
            click.echo(Fore.YELLOW + f"    [AVISO] Snapshot canônico '{snapshot_path}' não encontrado. Crie-o com 'doxoade canonize'.")
            continue

        with open(snapshot_path, 'r', encoding='utf-8') as f:
            canonical_output = f.read()

        normalized_current = current_output_formatted.replace('\r\n', '\n').strip()
        normalized_canonical = canonical_output.replace('\r\n', '\n').strip()

        if normalized_current == normalized_canonical:
            click.echo(Fore.GREEN + f"    [OK] Teste '{case_id}' passou.")
        else:
            failures += 1
            click.echo(Fore.RED + Style.BRIGHT + f"    [FALHA] Regressão detectada em '{case_id}'!")
            click.echo(Style.DIM + "--- SAÍDA ESPERADA (Cânone) ---")
            click.echo(Style.DIM + canonical_output.strip())
            click.echo(Style.DIM + "--- SAÍDA ATUAL ---")
            click.echo(Style.DIM + current_output_formatted.strip())
            
    # --- UTILITARIO 3: Relatório Final ---
    click.echo(Fore.CYAN + "\n--- Concluído ---")
    if failures > 0:
        click.echo(Fore.RED + f"{failures} teste(s) de regressão falharam.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "Todos os testes de regressão passaram com sucesso.")