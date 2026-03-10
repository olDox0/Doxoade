# doxoade/commands/fix.py
from pathlib import Path
import click

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger
from ..tools.import_fixer import fix_project_imports, verify_project_imports


@click.command('fix')
@click.option('--imports', 'fix_imports', is_flag=True, help='Corrige imports quebrados por arquivos/módulos movidos.')
@click.option('--import-verify', 'import_verify', is_flag=True, help='Apenas verifica imports suspeitos sem modificar arquivos.')
@click.argument('path', required=False, type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path))
def fix(fix_imports: bool, import_verify: bool, path: Path | None):
    """Sistema de auto-correção do projeto."""
    target = (path or Path('.')).resolve()
    root = target if target.is_dir() else target.parent

    params = {"imports": fix_imports, "import_verify": import_verify, "path": str(target)}
    with ExecutionLogger('fix', str(root), params):
        if not fix_imports and not import_verify:
            click.echo(f"{Fore.YELLOW}Nenhuma ação selecionada. Use --imports ou --import-verify.{Style.RESET_ALL}")
            return

        if fix_imports and import_verify:
            click.echo(f"{Fore.YELLOW}Escolha apenas um modo: --imports ou --import-verify.{Style.RESET_ALL}")
            return

        if import_verify:
            click.echo(f"{Fore.CYAN}--- [FIX] Verificando imports locais (somente leitura) ---{Style.RESET_ALL}")
            result = verify_project_imports(root)
            if result.imports_changed == 0:
                click.echo(f"{Fore.GREEN}Nenhum problema de import local detectado.{Style.RESET_ALL}")
                return
            click.echo(f"{Fore.YELLOW}Arquivos com suspeita: {result.files_changed}{Style.RESET_ALL}")
            click.echo(f"{Fore.YELLOW}Imports sinalizados: {result.imports_changed}{Style.RESET_ALL}")
            for line in result.details[:60]:
                click.echo(f"  {Fore.WHITE}• {line}{Style.RESET_ALL}")
            if len(result.details) > 60:
                click.echo(f"  {Style.DIM}... e mais {len(result.details)-60} ocorrência(s).{Style.RESET_ALL}")
            return

        click.echo(f"{Fore.CYAN}--- [FIX] Reescrevendo imports locais ---{Style.RESET_ALL}")
        result = fix_project_imports(root)

        if result.imports_changed == 0:
            click.echo(f"{Fore.GREEN}Nenhum import local precisou de ajuste.{Style.RESET_ALL}")
            return

        click.echo(f"{Fore.GREEN}Arquivos alterados: {result.files_changed}{Style.RESET_ALL}")
        click.echo(f"{Fore.GREEN}Imports ajustados: {result.imports_changed}{Style.RESET_ALL}")
        for line in result.details[:40]:
            click.echo(f"  {Fore.WHITE}• {line}{Style.RESET_ALL}")
        if len(result.details) > 40:
            click.echo(f"  {Style.DIM}... e mais {len(result.details)-40} ajuste(s).{Style.RESET_ALL}")
