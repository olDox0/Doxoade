# doxoade/commands/fix.py
from pathlib import Path
import click

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger
from ..tools.import_fixer import fix_project_imports


@click.command('fix')
@click.option('--imports', 'fix_imports', is_flag=True, help='Corrige imports quebrados por arquivos/módulos movidos.')
def fix(fix_imports: bool):
    """Sistema de auto-correção do projeto."""
    params = {"imports": fix_imports}
    with ExecutionLogger('fix', '.', params):
        if not fix_imports:
            click.echo(f"{Fore.YELLOW}Nenhuma ação selecionada. Use --imports.{Style.RESET_ALL}")
            return

        click.echo(f"{Fore.CYAN}--- [FIX] Reescrevendo imports locais ---{Style.RESET_ALL}")
        result = fix_project_imports(Path('.').resolve())

        if result.imports_changed == 0:
            click.echo(f"{Fore.GREEN}Nenhum import local precisou de ajuste.{Style.RESET_ALL}")
            return

        click.echo(f"{Fore.GREEN}Arquivos alterados: {result.files_changed}{Style.RESET_ALL}")
        click.echo(f"{Fore.GREEN}Imports ajustados: {result.imports_changed}{Style.RESET_ALL}")
        for line in result.details[:40]:
            click.echo(f"  {Fore.WHITE}• {line}{Style.RESET_ALL}")
        if len(result.details) > 40:
            click.echo(f"  {Style.DIM}... e mais {len(result.details)-40} ajuste(s).{Style.RESET_ALL}")
