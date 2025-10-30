# DEV.V10-20251022. >>>
# doxoade/commands/self_test.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 2.1(Fnc).
# Descrição: CORREÇÃO DE ROBUSTEZ FINAL. A função de subprocesso agora usa 'sys.getdefaultencoding()'
# e a verificação de erro foi aprimorada para lidar com múltiplas saídas.

import os, sys, subprocess, tempfile, shutil, click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger

# No início do arquivo self_test.py
TEST_CASES = {
    "check": {
        "filename": "broken_code.py",
        "content": "def funcao_quebrada():\\n    pass # Erro de sintaxe aqui, ':' faltando na linha anterior",
        "expected_finding": "Erro de sintaxe impede a analise" # ASCII PURO, sem ponto final
    },
    "webcheck": {
        "filename": "broken_page.html",
        "content": '<a href="pagina_inexistente.html">Link Quebrado</a>',
        "expected_finding": "Link quebrado para 'pagina_inexistente.html'"
    }
}

def _run_doxoade_in_sandbox(command_to_test, sandbox_path):
    """Executa um comando doxoade dentro de um diretório sandbox de forma robusta."""
    
    runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
    if not runner_path:
        return -1, "Não foi possível encontrar o executável 'doxoade' no PATH."

    command = [runner_path] + command_to_test.split()
    
    try:
        # --- A CORREÇÃO CRÍTICA DE ROBUSTEZ ---
        # Usa a codificação padrão do sistema e substitui erros para evitar falhas.
        result = subprocess.run(
            command, 
            cwd=sandbox_path, 
            capture_output=True, 
            text=True, 
            encoding=sys.getdefaultencoding(), 
            errors='replace'
        )
        
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return result.returncode, stdout + stderr
    except Exception as e:
        return -1, f"Ocorreu um erro inesperado ao executar o subprocesso: {e}"

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

            # --- LÓGICA DE DIAGNÓSTICO INTELIGENTE (JÁ ESTAVA CORRETA) ---

            click.echo("\n--- [DEPURAÇÃO DE BYTES] ---")
            click.echo(f"Output (bytes):       {output.encode('utf-8', 'replace')}")
            click.echo(f"Expected (bytes):     {test_case['expected_finding'].encode('utf-8', 'replace')}")
            click.echo(f"Match found:          {test_case['expected_finding'] in output}")
            click.echo("--- [FIM DA DEPURAÇÃO] ---\n")
            # --- FIM DA LÓGICA DE DEPURAÇÃO ---

            # --- LÓGICA DE DIAGNÓSTICO FINAL E ROBUSTA ---
            failed_as_expected = return_code != 0
            
            # Normaliza ambas as strings para ASCII puro, ignorando caracteres problemáticos.
            normalized_output = output.encode('ascii', 'ignore').decode('ascii')
            normalized_expected = test_case["expected_finding"].encode('ascii', 'ignore').decode('ascii')
            
            found_specific_error = normalized_expected in normalized_output
            
            if failed_as_expected and found_specific_error:
                logger.add_finding('INFO', f"O comando '{command_name}' detectou o erro específico com sucesso.")
                click.echo(Fore.GREEN + Style.BRIGHT + "\n[OK] SUCESSO: O analisador detectou o erro específico esperado.")
            
            elif failed_as_expected and not found_specific_error:
                logger.add_finding('CRITICAL', f"O '{command_name}' falhou, mas não pelo motivo esperado.", details=output)
                click.echo(Fore.RED + Style.BRIGHT + "\n[FALHA DE DIAGNÓSTICO] O analisador falhou, mas não pelo motivo correto.")
                click.echo(Fore.WHITE + "   > Ele deveria ter encontrado: " + Fore.YELLOW + test_case["expected_finding"])
                if not debug:
                    click.echo(Fore.WHITE + "   > A saída completa está abaixo para análise.")
                    click.echo(output)
                sys.exit(1)

            elif not failed_as_expected:
                logger.add_finding('CRITICAL', f"O comando '{command_name}' falhou em detectar um erro óbvio.", details=output)
                click.echo(Fore.RED + Style.BRIGHT + "\n[FALHA CRÍTICA] O analisador está sofrendo de uma 'falha silenciosa'.")
                if not debug: click.echo(output)
                sys.exit(1)

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