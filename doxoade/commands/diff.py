# -*- coding: utf-8 -*-
"""
Módulo de Diferenciação Git (Diff).
Exibe alterações entre o estado atual e revisões históricas.
"""
import os
import sys
import click
from colorama import Fore
from ..shared_tools import ExecutionLogger, _run_git_command, _present_diff_output

@click.command('diff')
@click.argument('path', type=click.Path(exists=True))
@click.option('-v', '--revision', 'revision_hash', help="Hash do commit para comparação.")
def diff(path, revision_hash):
    """Analisa diferenças de código via Git."""
    if not path:
        raise ValueError("Caminho é obrigatório.")

    with ExecutionLogger('diff', path, {'revision': revision_hash}) as logger:
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True, silent_fail=True)
        
        if not git_root:
            click.echo(Fore.RED + "[ERRO] Este diretório não é um repositório Git.")
            return

        relative_path = os.path.relpath(os.path.abspath(path), git_root)
        
        # Define o alvo (Revision ou HEAD)
        target = revision_hash if revision_hash else "HEAD"
        
        cmd = ['diff', target, '--', relative_path]
        result = _run_git_command(cmd, capture_output=True)
        
        if not result:
            click.echo(Fore.GREEN + "Nenhuma diferença detectada.")
        else:
            click.echo(Fore.CYAN + f"--- Diferenças em '{relative_path}' vs {target} ---")
            # Agora a função existe e está importada corretamente
            _present_diff_output(result)