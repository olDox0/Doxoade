# doxoade/commands/auto.py
import sys
import subprocess
import os
import click
import shlex
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger

__version__ = "37.0 Alfa (Interactive Pipelines)"

def _execute_command(command_str, inputs=None):
    """
    (Versão Corrigida) Executa um comando, lida com inputs e força a saída colorida.
    """
    
    click.echo(Fore.YELLOW + f"   > Executando: {command_string}")
    
    # [SEGURANÇA] shlex para dividir a string em argumentos seguros
    
    try:
        args = shlex.split(command_string)
    except ValueError as e:
        click.echo(Fore.RED + f"   > Erro de sintaxe no comando: {e}")
        return 1
    
    try:
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["PYTHONIOENCODING"] = "UTF-8"

        input_str = "\n".join(inputs) + "\n" if inputs else None

        # --- A ÚNICA MUDANÇA ESTÁ AQUI ---
        # Passamos a string do comando diretamente, sem tentar dividi-la primeiro.
        # O 'shell=True' cuidará de interpretar a string corretamente.
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE if input_str else None,
            stdout=sys.stdout, 
            stderr=sys.stderr,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            shell=False 
        )
        if input_str:
            process.communicate(input=input_str)
        else:
            process.wait()

        return process.returncode

    except FileNotFoundError:
        click.echo(Fore.RED + f"   > Comando não encontrado: {args[0]}")
        return 1
    except Exception as e:
        click.echo(Fore.RED + f"   > Erro inesperado ao executar comando: {e}")
        return 1

@click.command('auto')
@click.argument('prompt', required=False)
@click.option('--file', '-f', multiple=True, help="Arquivos de contexto para a IA.")
def auto(prompt, file):
    """Executa uma sequência de comandos como um pipeline robusto."""
    arguments = ctx.params
    
    # --- PARSER DA NOVA SINTAXE DE PIPELINE ---
    pipeline_steps = []
    source_lines = []

    if filepath:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
        except IOError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao ler o arquivo de pipeline: {e}"); sys.exit(1)
    elif commands:
        source_lines = list(commands)

    temp_inputs = []
    for line in source_lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('ECHO:'):
            pipeline_steps.append({'type': 'echo', 'value': line[5:].strip()})
        elif line.startswith('>'):
            temp_inputs.append(line[1:].strip())
        else:
            pipeline_steps.append({'type': 'command', 'value': line, 'inputs': temp_inputs})
            temp_inputs = []
    # --- FIM DO PARSER ---

    with ExecutionLogger('auto', '.', arguments) as logger:
        if not pipeline_steps:
            click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {len(pipeline_steps)} passo(s) ---")
        
        results = []
        final_success = True

        for i, step in enumerate(pipeline_steps, 1):
            if step['type'] == 'echo':
                click.echo(Fore.MAGENTA + Style.BRIGHT + f"\n--- [AUTO] {step['value']} ---")
                continue

            command_str = step['value']
            inputs = step['inputs']
            
            click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{len(pipeline_steps)}: {command_str} ---")
            
            return_code = _execute_command(command_str, inputs)
            
            status = "sucesso" if return_code == 0 else "falha"
            results.append({"command": command_str, "status": status, "returncode": return_code})
            
            if status == "falha": final_success = False
            
        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- [AUTO] Sumário do Pipeline ---")
        for res in results:
            if res["status"] == "sucesso":
                click.echo(Fore.GREEN + f"[OK] Sucesso -> {res['command']}")
            else:
                click.echo(Fore.RED + f"[ERRO] Falha (código {res['returncode']}) -> {res['command']}")
        click.echo("-" * 40)
        
        if final_success:
            click.echo(Fore.GREEN + Style.BRIGHT + "[SUCESSO] Pipeline concluído com sucesso!")
        else:
            logger.add_finding('error', "Pipeline executado, mas um ou mais passos falharam.")
            click.echo(Fore.RED + Style.BRIGHT + "[ATENÇÃO] Pipeline executado, mas um ou mais passos falharam.")
            sys.exit(1)