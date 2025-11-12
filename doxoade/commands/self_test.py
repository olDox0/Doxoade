import os
import sys
import subprocess
import tempfile
import shutil
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger

TEST_CASES = {
    "check": {
        "filename": "broken_code.py",
        "content": "def funcao_quebrada()\n    pass",
        "expected_finding": "invalid syntax"
    },
    "webcheck": {
        "filename": "broken_page.html",
        "content": '<a href="pagina_inexistente.html">Link Quebrado</a>',
        "expected_finding": "Link quebrado para 'pagina_inexistente.html'"
    }
}

def _setup_test_env(project_dir):
    """Cria um venv e instala o pyflakes nele para um teste realista."""
    try:
        subprocess.run([sys.executable, "-m", "venv", os.path.join(project_dir, "venv")], check=True, capture_output=True)
        venv_python = os.path.join(project_dir, "venv", "Scripts" if sys.platform == "win32" else "bin", "python")
        subprocess.run([venv_python, "-m", "pip", "install", "pyflakes"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Permite que o teste continue e falhe no diagnóstico, o que é informativo.
        pass

def _run_doxoade_in_sandbox(command_to_test, sandbox_path):
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path:
        return -1, "Não foi possível encontrar o executável 'doxoade' no PATH."
    command = [runner_path] + command_to_test.split()
    try:
        result = subprocess.run(
            command, cwd=sandbox_path, capture_output=True, text=True, 
            encoding=sys.getdefaultencoding(), errors='backslashreplace'
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return -1, f"Ocorreu um erro inesperado: {e}"

@click.command('self-test')
@click.argument('command_name', type=click.Choice(list(TEST_CASES.keys())), default='check')
@click.option('--debug', is_flag=True, help="Exibe a saída completa do comando analisado.")
@click.pass_context
def self_test(ctx, command_name, debug):
    """Executa um teste de sanidade em um analisador da doxoade."""
    path = '.'
    arguments = ctx.params
    with ExecutionLogger('self-test', path, arguments) as logger:
        click.echo(Fore.CYAN + f"--- [SELF-TEST] Verificando a sanidade do comando '{command_name}' ---")
        test_case = TEST_CASES[command_name]
        with tempfile.TemporaryDirectory() as sandbox:
            click.echo(Fore.WHITE + Style.DIM + f"   > Sandbox criado em: {sandbox}")
            _setup_test_env(sandbox)
            file_to_create = os.path.join(sandbox, test_case["filename"])
            with open(file_to_create, "w", encoding="utf-8") as f:
                f.write(test_case["content"])
            click.echo(Fore.WHITE + Style.DIM + f"   > Arquivo de teste '{test_case['filename']}' implantado.")
            click.echo(Fore.YELLOW + f"   > Executando '{command_name}' contra o erro conhecido...")
            return_code, output = _run_doxoade_in_sandbox(f"{command_name} .", sandbox)
            if debug:
                click.echo(Fore.WHITE + Style.DIM + f"\n--- [DEBUG] Saída ---\n{output}\n--- [DEBUG] Código: {return_code} ---\n")
            
            failed_as_expected = return_code != 0
            normalized_output = output.encode('ascii', 'ignore').decode('ascii')
            normalized_expected = test_case["expected_finding"].encode('ascii', 'ignore').decode('ascii')
            found_specific_error = normalized_expected in normalized_output
            
            if failed_as_expected and found_specific_error:
                logger.add_finding('INFO', f"O comando '{command_name}' detectou o erro com sucesso.")
                click.echo(Fore.GREEN + Style.BRIGHT + "\n[OK] SUCESSO: O analisador detectou o erro esperado.")
            elif failed_as_expected and not found_specific_error:
                logger.add_finding('CRITICAL', "O analisador falhou, mas não pelo motivo correto.", details=output)
                click.echo(Fore.RED + Style.BRIGHT + "\n[FALHA DE DIAGNÓSTICO]")
                sys.exit(1)
            elif not failed_as_expected:
                logger.add_finding('CRITICAL', "O analisador sofreu uma 'falha silenciosa'.", details=output)
                click.echo(Fore.RED + Style.BRIGHT + "\n[FALHA CRÍTICA] 'Falha silenciosa' detectada.")
                sys.exit(1)