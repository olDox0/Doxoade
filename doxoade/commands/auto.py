# doxoade/commands/auto.py
import sys
import subprocess
import shlex
import signal
import threading
import shutil

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

__version__ = "35.6 Alfa (Phoenix)"

def _execute_command(command_to_run, is_interactive, original_sigint_handler):
    """Executa um comando de forma interativa ou não-interativa."""
    if is_interactive:
        click.echo(Fore.YELLOW + "[AUTO] Comando interativo detectado. Cedendo controle...")
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            return subprocess.run(command_to_run, shell=False) # shell=False é mais seguro
        finally:
            signal.signal(signal.SIGINT, original_sigint_handler)
    else:
        process = subprocess.Popen(command_to_run, shell=False, text=True, encoding='utf-8', errors='replace',
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def _stream_reader(pipe, color=None):
            for line in iter(pipe.readline, ''):
                output = color + line + Style.RESET_ALL if color else line
                sys.stdout.write(output)
                sys.stdout.flush()

        stdout_thread = threading.Thread(target=_stream_reader, args=[process.stdout])
        stderr_thread = threading.Thread(target=_stream_reader, args=[process.stderr, Fore.RED])
        
        stdout_thread.start(); stderr_thread.start()
        process.wait()
        stdout_thread.join(); stderr_thread.join()
        
        return process

@click.command('auto')
@click.pass_context
@click.argument('commands', nargs=-1, required=True)
def auto(ctx, commands):
    """Executa uma sequência de comandos como um pipeline robusto."""
    arguments = ctx.params
    with ExecutionLogger('auto', '.', arguments) as logger:
        if not commands:
            click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

        # A LÓGICA CRÍTICA QUE ESTAVA FALTANDO
        runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
        if not runner_path:
            click.echo(Fore.RED + "[AUTO ERRO] Runner 'doxoade.bat' não encontrado no PATH.")
            sys.exit(1)

        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {len(commands)} passo(s) ---")
        
        results = []
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        try:
            for i, command_str in enumerate(commands, 1):
                click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{len(commands)}: {command_str} ---")
                step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
                
                try:
                    args = shlex.split(command_str)
                    # Substituímos 'doxoade' pelo caminho absoluto do runner
                    command_to_run = [runner_path] + args[1:]
                    
                    is_interactive = any(cmd in command_str for cmd in ['run', 'tutorial interactive'])
                    
                    process_result = _execute_command(command_to_run, is_interactive, original_sigint_handler)

                    if process_result.returncode != 0:
                        step_result.update({"status": "falha", "returncode": process_result.returncode})
                
                except Exception as e:
                    step_result.update({"status": "falha", "error": str(e)})
                
                results.append(step_result)
                logger.add_finding('info', f"Passo '{command_str}' concluído com status: {step_result.get('status')}")

        except KeyboardInterrupt:
            click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n [AUTO] Pipeline cancelado pelo usuário.")
            sys.exit(1)
        finally:
            signal.signal(signal.SIGINT, original_sigint_handler)
            
        # ... (A lógica de sumário permanece a mesma)
        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- [AUTO] Sumário do Pipeline ---")
        final_success = True
        for i, result in enumerate(results, 1):
            if result.get("status") == "sucesso":
                click.echo(Fore.GREEN + f"[OK] Passo {i}: Sucesso -> {result.get('command')}")
            else:
                final_success = False
                error_details = result.get('error', f"código de saída {result.get('returncode', 'N/A')}")
                click.echo(Fore.RED + f"[ERRO] Passo {i}: Falha ({error_details}) -> {result.get('command')}")
        click.echo("-" * 40)
        
        if final_success:
            click.echo(Fore.GREEN + Style.BRIGHT + "[SUCESSO] Pipeline concluído com sucesso!")
        else:
            logger.add_finding('error', "Pipeline executado, mas um ou mais passos falharam.")
            click.echo(Fore.RED + Style.BRIGHT + "[ATENÇÃO] Pipeline executado, mas um ou mais passos falharam.")
            sys.exit(1)