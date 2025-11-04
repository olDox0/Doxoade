# doxoade/commands/canonize.py
import os
import sys
import subprocess
import toml
import click
from colorama import Fore

# Define os caminhos base para o sistema de regressão
REGRESSION_BASE_DIR = "regression_tests"
FIXTURES_DIR = os.path.join(REGRESSION_BASE_DIR, "fixtures")
CANON_DIR = os.path.join(REGRESSION_BASE_DIR, "canon")
CONFIG_FILE = os.path.join(REGRESSION_BASE_DIR, "canon.toml")

def _sanitize_output(text, project_path):
    """Substitui caminhos absolutos por um placeholder para portabilidade."""
    # Normaliza as barras para consistência entre OS
    normalized_path = os.path.normpath(project_path)
    # Substitui o caminho, ignorando diferenças de maiúsculas/minúsculas
    return text.replace(normalized_path, "<PROJECT_PATH>")

@click.command('canonize')
def canonize():
    """Executa os casos de teste de regressão e salva a saída como 'cânone'."""
    click.echo(Fore.CYAN + "--- [CANONIZE] Iniciando a criação de snapshots de regressão ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    if not test_cases:
        click.echo(Fore.YELLOW + "Nenhum caso de teste definido em 'canon.toml'.")
        return

    doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')
    os.makedirs(CANON_DIR, exist_ok=True)
    
    for case in test_cases:
        case_id = case.get('id')
        command = case.get('command')
        project_name = case.get('project')
        
        if not all([case_id, command, project_name]):
            click.echo(Fore.YELLOW + f"[AVISO] Ignorando caso de teste malformado: {case}")
            continue

        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        click.echo(Fore.WHITE + f"  > Executando teste '{case_id}'...")

        # --- A CORREÇÃO FINAL E DEFINITIVA ---
        # Cria um venv real dentro do projeto paciente
        subprocess.run([sys.executable, "-m", "venv", "venv"], cwd=project_path, check=True, capture_output=True)
        
        # Identifica o caminho para o executável do NOVO venv
        venv_python_path = os.path.join(project_path, "venv", "Scripts" if sys.platform == "win32" else "bin", "python")
        doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')

        # Constrói o comando usando o executável do venv do projeto principal
        full_command = command.replace("doxoade", f'"{doxoade_executable}"', 1)
        
        result = subprocess.run(
            full_command, cwd=project_path, capture_output=True, text=True, shell=True,
            # Usa a codificação do sistema para máxima compatibilidade
            encoding=sys.getdefaultencoding(), errors='replace'
        )
        
        sanitized_stdout = _sanitize_output(result.stdout, project_path)
        sanitized_stderr = _sanitize_output(result.stderr, project_path)

        snapshot_content = (
            f"--- COMMAND ---\n{command}\n\n"
            f"--- EXIT CODE ---\n{result.returncode}\n\n"
            f"--- STDOUT ---\n{sanitized_stdout}\n\n"
            f"--- STDERR ---\n{sanitized_stderr}\n"
        )
        
        # --- A CORREÇÃO CHAVE ---
        # Normaliza todos os finais de linha para o padrão Unix (\n)
        normalized_snapshot = snapshot_content.replace('\\r\\n', '\\n')

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.txt")
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            f.write(normalized_snapshot)
        
        click.echo(Fore.GREEN + f"    [OK] Snapshot '{snapshot_path}' criado/atualizado com sucesso.")

    click.echo(Fore.CYAN + "\n--- Concluído ---")