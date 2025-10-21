# doxoade/commands/clean.py
# atualizado em 2025/10/21 - Versão do projeto 42(Ver), Versão da função 2.0(Fnc).
# Descrição: Aprimora o tratamento de erro para detectar falhas de permissão e sugerir a execução com privilégios de administrador.
import os
from colorama import Fore
from pathlib import Path
import click
import shutil

from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.command('clean')
@click.pass_context
@click.option('--force', '-f', is_flag=True, help="Força a limpeza sem pedir confirmação.")
def clean(ctx, force):
    """Remove arquivos de cache e build do projeto."""
    arguments = ctx.params
    path = '.'

    with ExecutionLogger('clean', path, arguments) as logger:
        click.echo(Fore.CYAN + "-> [CLEAN] Procurando por artefatos de build e cache...")
        
        TARGET_PATTERNS = ["__pycache__", "build", "dist", ".pytest_cache", ".tox", "*.egg-info", "*.spec"]
        
        all_paths = [p for pattern in TARGET_PATTERNS for p in Path('.').rglob(pattern)]
        
        targets_to_delete = {p for p in all_paths if 'venv' not in p.parts and '.git' not in p.parts}

        if not targets_to_delete:
            click.echo(Fore.GREEN + "[OK] O projeto já está limpo.")
            return

        click.echo(Fore.YELLOW + f"Encontrados {len(targets_to_delete)} itens para remover:")
        for target in sorted(targets_to_delete):
            click.echo(f"  - {target}")

        if not force and not click.confirm(f"\n{Fore.YELLOW}Remover permanentemente estes itens?"):
            click.echo(Fore.CYAN + "\nOperação cancelada.")
            return

        click.echo(Fore.CYAN + "\n-> Iniciando a limpeza...")
        deleted_count = 0
        for target in sorted(targets_to_delete, reverse=True):
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                    click.echo(f"  {Fore.GREEN}Removido diretório: {target}")
                elif target.is_file():
                    target.unlink()
                    click.echo(f"  {Fore.GREEN}Removido arquivo: {target}")
                deleted_count += 1
            except OSError as e:
                error_message = f"Erro ao remover {target}: {e}"
                # No Windows, 'Acesso negado' é o WinError 5 ou PermissionError. No Linux, é o errno 13.
                if (os.name == 'nt' and isinstance(e, PermissionError)) or (hasattr(e, 'winerror') and e.winerror == 5) or (hasattr(e, 'errno') and e.errno == 13):
                    error_message += "\n     Dica: Tente executar o comando em um terminal com privilégios de administrador."
                
                logger.add_finding('error', f"Erro ao remover {target}: {e}")
                click.echo(Fore.RED + f"  {error_message}", err=True)
        
        logger.add_finding('info', f"{deleted_count} itens removidos.")
        click.echo(Fore.GREEN + f"\n Limpeza concluída! {deleted_count} itens foram removidos.")