# DEV.V10-20251022. >>>
# doxoade/commands/self_test.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 1.2(Fnc).
# Descrição: Adiciona uma flag '--debug' para exibir a saída completa do comando
# analisado, fornecendo total transparência ao teste de sanidade.

import os
import sys
import subprocess
import tempfile
import shutil
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

# Dicionário de "Pacientes Zero": Mapeia um comando para o código que deve fazê-lo falhar.
TEST_CASES = {
    "check": {
        "filename": "broken_code.py",
        "content": "def funcao_quebrada()\\n    pass", # SyntaxError
        "expected_fail": True
    },
    "webcheck": {
        "filename": "broken_page.html",
        "content": '<a href="pagina_inexistente.html">Link Quebrado</a>',
        "expected_fail": True
    }
    # Podemos adicionar mais casos aqui no futuro.
}

def _run_doxoade_in_sandbox(command_to_test, sandbox_path):
    """Executa um comando doxoade dentro de um diretório sandbox."""
    
    # Encontra o executável da doxoade que está sendo usado no momento
    runner_path = shutil.which("doxoade")
    if not runner_path:
        return -1, "Não foi possível encontrar o executável 'doxoade' no PATH."

    command = [runner_path] + command_to_test.split()
    
    # Executa o comando, apontando para o diretório sandbox
    result = subprocess.run(command, cwd=sandbox_path, capture_output=True, text=True, encoding='utf-8')
    
    return result.returncode, result.stdout + result.stderr

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
            
            # Implanta o arquivo quebrado no sandbox
            file_to_create = os.path.join(sandbox, test_case["filename"])
            with open(file_to_create, "w") as f:
                f.write(test_case["content"])
            click.echo(Fore.WHITE + Style.DIM + f"   > Arquivo de teste '{test_case['filename']}' implantado.")
            
            click.echo(Fore.YELLOW + f"   > Executando '{command_name}' contra o erro conhecido...")
            return_code, output = _run_doxoade_in_sandbox(f"{command_name} .", sandbox)

            if debug:
                click.echo(Fore.WHITE + Style.DIM + "\n--- [DEBUG] Saída do Comando Analisado ---")
                click.echo(output)
                click.echo(Fore.WHITE + Style.DIM + f"--- [DEBUG] Código de Saída: {return_code} ---\n")

            # Diagnóstico do Diagnóstico
            if test_case["expected_fail"] and return_code != 0:
                logger.add_finding('INFO', f"O comando '{command_name}' detectou o erro com sucesso.")
                click.echo(Fore.GREEN + Style.BRIGHT + "\n[OK] SUCESSO: O analisador detectou o erro como esperado.")
            elif test_case["expected_fail"] and return_code == 0:
                logger.add_finding('CRITICAL', f"O comando '{command_name}' falhou em detectar um erro óbvio.", details=output)
                click.echo(Fore.RED + Style.BRIGHT + "\n[FALHA CRÍTICA] O analisador está sofrendo de uma 'falha silenciosa'.")
                click.echo(Fore.WHITE + "   > Saída do comando (que deveria ter falhado):\n" + output)
                sys.exit(1)
            else:
                # Cenários para testes que deveriam passar (não implementado ainda)
                logger.add_finding('ERROR', "Lógica de teste inesperada.", details=f"Return code: {return_code}")
                click.echo(Fore.RED + "\n[ERRO] Resultado inesperado do teste.")
                
def _run_doxoade_in_sandbox(command_to_test, sandbox_path):
    """Executa um comando doxoade dentro de um diretório sandbox de forma robusta."""
    
    runner_path = shutil.which("doxoade")
    if not runner_path:
        return -1, "Não foi possível encontrar o executável 'doxoade' no PATH."

    command = [runner_path] + command_to_test.split()
    
    try:
        # --- INÍCIO DA CORREÇÃO ---
        # 1. 'capture_output=True' substitui a necessidade de gerenciar pipes manualmente.
        # 2. 'encoding=sys.getdefaultencoding()' usa a codificação correta do terminal, evitando o UnicodeDecodeError.
        result = subprocess.run(
            command, 
            cwd=sandbox_path, 
            capture_output=True, 
            text=True, 
            encoding=sys.getdefaultencoding(), # <--- CORREÇÃO DE ENCODING
            errors='replace'
        )
        
        # 3. Trata saídas 'None' antes de concatenar, resolvendo o TypeError.
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        # --- FIM DA CORREÇÃO ---

        return result.returncode, stdout + stderr
    except FileNotFoundError:
        return -1, f"Comando '{runner_path}' não encontrado. A instalação do doxoade pode estar quebrada."
    except Exception as e:
        return -1, f"Ocorreu um erro inesperado ao executar o subprocesso: {e}"