# doxoade/doxoade/probes/command_wrapper.py
import sys
import os
from click.testing import CliRunner
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)
from doxoade.cli import cli

def run_internal_command(command_name, args):
    """
    Simula a execução de um comando interno do Doxoade para análise de Flow.
    """
    print(f"--- [WRAPPER] Preparando para rodar: doxoade {command_name} {' '.join(args)} ---")
    runner = CliRunner()
    result = runner.invoke(cli, [command_name] + args)
    if result.exit_code != 0:
        print('[WRAPPER ERROR] Comando falhou:')
        print(result.output)
        if result.exception:
            raise result.exception
    else:
        print('[WRAPPER SUCCESS] Comando finalizado.')
        print(result.output)
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python command_wrapper.py <comando> [args...]')
        sys.exit(1)
    cmd = sys.argv[1]
    arguments = sys.argv[2:]
    run_internal_command(cmd, arguments)
