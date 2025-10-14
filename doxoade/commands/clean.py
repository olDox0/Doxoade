# doxoade/commands/clean.py
from colorama import Fore
from pathlib import Path
import click
import shutil

# Importa as ferramentas necessárias do módulo compartilhado
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
                    click.echo(f"  {Fore.RED}Removido diretório: {target}")
                elif target.is_file():
                    target.unlink()
                    click.echo(f"  {Fore.RED}Removido arquivo: {target}")
                deleted_count += 1
            except OSError as e:
                logger.add_finding('error', f"Erro ao remover {target}: {e}")
                click.echo(Fore.RED + f"  Erro ao remover {target}: {e}", err=True)
        
        logger.add_finding('info', f"{deleted_count} itens removidos.")
        click.echo(Fore.GREEN + f"\n Limpeza concluída! {deleted_count} itens foram removidos.")