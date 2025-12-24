# doxoade/commands/exec.py
import sys
import subprocess
import click
from colorama import Fore, Style

# O truque aqui é que o @click e a estrutura do Doxoade já acionam o Chronos
# no cli.py. O Chronos atualizado (Step 1) vai monitorar automaticamente 
# os filhos gerados por este comando.

@click.command('exec', context_settings=dict(ignore_unknown_options=True))
@click.argument('cmd_args', nargs=-1, type=click.UNPROCESSED)
def exec_cmd(cmd_args):
    """
    Executa qualquer comando arbitrário com monitoramento de telemetria (MaxTelemetry).
    Uso: doxoade exec -- <comando> [args]
    Ex:  doxoade exec -- npm install
    """
    if not cmd_args:
        click.echo(Fore.YELLOW + "Uso: doxoade exec -- <comando>")
        return

    # Converte tupla para lista
    command = list(cmd_args)
    
    click.echo(Fore.CYAN + f"--- [EXEC] Monitorando: {' '.join(command)} ---")
    
    try:
        # Executa o comando e espera terminar
        # shell=False para segurança, a menos que seja explicitamente um shell script
        # O Chronos (em background) vai somar o uso de CPU/RAM deste subprocesso
        result = subprocess.run(command)
        
        if result.returncode != 0:
            sys.exit(result.returncode)
            
    except FileNotFoundError:
        click.echo(Fore.RED + f"[ERRO] Comando não encontrado: {command[0]}")
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[INTERROMPIDO] Execução cancelada.")