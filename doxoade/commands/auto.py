# doxoade/commands/auto.py
# atualizado em 2025/10/21 - Versão do projeto 42(Ver), Versão da função 3.0(Fnc).
# Descrição: Reintroduz a opção '--file' para restaurar a funcionalidade de pipeline a partir de arquivos.
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

# Esta função de execução permanece a mesma, pois é robusta.
def _execute_command(command_to_run, is_interactive, original_sigint_handler):
    if is_interactive:
        click.echo(Fore.YELLOW + "[AUTO] Comando interativo detectado. Cedendo controle...")
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            return subprocess.run(command_to_run, shell=False)
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
@click.argument('commands', nargs=-1, required=False) # Tornou-se opcional
@click.option('--file', 'filepath', type=click.Path(exists=True, dir_okay=False), help="Executa um pipeline a partir de um arquivo.")
def auto(ctx, commands, filepath):
    """Executa uma sequência de comandos como um pipeline robusto."""
    arguments = ctx.params
    
    # --- NOVO UTILITÁRIO 1: CARREGAR COMANDOS ---
    commands_to_run = []
    if filepath:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                commands_to_run = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except IOError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao ler o arquivo de pipeline: {e}")
            sys.exit(1)
    elif commands:
        commands_to_run = list(commands)
    # --- FIM DO UTILITÁRIO ---

    with ExecutionLogger('auto', '.', arguments) as logger:
        if not commands_to_run:
            click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

        runner_path = shutil.which("doxoade.bat") or shutil.which("doxoade")
        if not runner_path:
            click.echo(Fore.RED + "[AUTO ERRO] Runner 'doxoade' não encontrado no PATH.")
            sys.exit(1)

        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {len(commands_to_run)} passo(s) ---")
        
        results = []
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        try:
            for i, command_str in enumerate(commands_to_run, 1):
                click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{len(commands_to_run)}: {command_str} ---")
                step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
                
                try:
                    args = shlex.split(command_str)
                    command_to_run_abs = [runner_path] + args[1:]
                    
                    is_interactive = any(cmd in command_str for cmd in ['run', 'tutorial interactive'])
                    
                    process_result = _execute_command(command_to_run_abs, is_interactive, original_sigint_handler)

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