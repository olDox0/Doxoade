# -*- coding: utf-8 -*-
# doxoade/commands/auto.py
import sys
import os
import click
import shlex
from colorama import Fore #, Style
from ..shared_tools import ExecutionLogger

__version__ = "37.0 Alfa (Interactive Pipelines)"

def _execute_command(command_string: str, env: dict, inputs: list = None): # FIX: Mantido 'inputs'
    """Executa comando com proteção Aegis."""
    import subprocess
    import shlex
    click.echo(Fore.YELLOW + f"   > Executando: {command_string}")
    
    try:
        args = shlex.split(command_string)
        process = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, text=True, env=env, shell=False
        )
        if inputs: # FIX: Sincronizado com o argumento
            out, _ = process.communicate(input="\n".join(inputs))
            return out
        process.wait()
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
    
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

    except FileNotFoundError as e:
        click.echo(Fore.RED + f"   > Comando não encontrado: {args[0]}")
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return 1
    except Exception as e:
        click.echo(Fore.RED + f"   > Erro inesperado ao executar comando: {e}")
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)

        return 1
    return ""

@click.command('auto')
@click.argument('prompt', required=False)
@click.option('--file', '-f', 'filepath', multiple=True, help="Arquivos de contexto para a IA.")
@click.pass_context
def auto(ctx, prompt, filepath):
    """Executa uma sequência de comandos como um pipeline robusto."""
    arguments = ctx.params
# [DOX-UNUSED]     params = ctx.params
    commands = []
    # --- PARSER DA NOVA SINTAXE DE PIPELINE ---
    pipeline_steps = []
    source_lines = []

    if filepath:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
        except IOError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao ler o arquivo de pipeline: {e}"); sys.exit(1)
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
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