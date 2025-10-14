# doxoade/commands/auto.py
import sys
import subprocess
import tempfile
import shlex
import signal
import threading

import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.command('auto')
@click.pass_context
@click.argument('commands', nargs=-1, required=True)
def auto(ctx, commands):
    """Executa uma sequência de comandos como um pipeline robusto."""
    arguments = ctx.params
    path = '.'
    
    with ExecutionLogger('auto', path, arguments) as logger:
        if not commands:
            click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

        total_commands = len(commands)
        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {total_commands} passo(s) ---")
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=True, suffix='.dox', encoding='utf-8') as temp_pipeline:
            for command in commands:
                temp_pipeline.write(f"{command}\n")
            temp_pipeline.flush()
            temp_pipeline.seek(0)
            commands_to_run = [line.strip() for line in temp_pipeline if line.strip() and not line.strip().startswith('#')]

        results = []
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        try:
            for i, command_str in enumerate(commands_to_run, 1):
                click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{total_commands}: {command_str} ---")
                step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
                
                try:
                    args = shlex.split(command_str)
                    is_interactive = 'run' in args and 'doxoade' in args

                    if is_interactive:
                        click.echo(Fore.YELLOW + "[AUTO] Comando interativo detectado. Cedendo controle...")
                        try:
                            signal.signal(signal.SIGINT, signal.SIG_IGN)
                            process_result = subprocess.run(command_str, shell=True, text=True, encoding='utf-8', errors='replace')
                        finally:
                            signal.signal(signal.SIGINT, original_sigint_handler)
                        
                        if process_result.returncode != 0:
                            step_result["status"] = "falha"; step_result["returncode"] = process_result.returncode
                    else:
                        process = subprocess.Popen(args, shell=True, text=True, encoding='utf-8', errors='replace',
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                        def _stream_reader(pipe, color=None):
                            for line in iter(pipe.readline, ''):
                                output = color + line + Style.RESET_ALL if color else line
                                sys.stdout.write(output)

                        stdout_thread = threading.Thread(target=_stream_reader, args=[process.stdout])
                        stderr_thread = threading.Thread(target=_stream_reader, args=[process.stderr, Fore.RED])
                        stdout_thread.start(); stderr_thread.start()
                        process.wait(); stdout_thread.join(); stderr_thread.join()

                        if process.returncode != 0:
                            step_result["status"] = "falha"; step_result["returncode"] = process.returncode
                except Exception as e:
                    step_result["status"] = "falha"; step_result["error"] = str(e)
                
                results.append(step_result)
                logger.add_finding('info', f"Passo '{command_str}' concluído com status: {step_result['status']}")

        except KeyboardInterrupt:
            click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n [AUTO] Pipeline cancelado pelo usuário.")
            sys.exit(1)
        finally:
            signal.signal(signal.SIGINT, original_sigint_handler)
            
        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- [AUTO] Sumário do Pipeline ---")
        final_success = True
        for i, result in enumerate(results, 1):
            if result["status"] == "sucesso":
                click.echo(Fore.GREEN + f"[OK] Passo {i}: Sucesso -> {result['command']}")
            else:
                final_success = False
                error_details = result.get('error', f"código de saída {result.get('returncode', 'N/A')}")
                click.echo(Fore.RED + f"[ERRO] Passo {i}: Falha ({error_details}) -> {result['command']}")
        click.echo("-" * 40)
        
        if not final_success:
            logger.add_finding('error', "Pipeline executado, mas um ou mais passos falharam.")
            sys.exit(1)