# doxoade/commands/purge_history.py
import click
import os
from doxoade.tools.doxcolors import Fore, Style, Back
from ..shared_tools import ExecutionLogger, _find_project_root
@click.command('purge-history')
@click.argument('patterns', nargs=-1, required=True)
@click.option('--dry-run', is_flag=True, help="Apenas analisa o impacto sem deletar.")
@click.option('--yes-i-know-what-i-am-doing', is_flag=True, help="Ignora o aviso de segurança.")
@click.pass_context
def purge_history(ctx, patterns, dry_run, yes_i_know_what_i_am_doing):
    """☢ [NUCLEAR] Remove arquivos permanentemente de TODO o histórico Git.
    
    Exemplo: doxoade purge-history ".doxoade/cache/*" "*.log"
    Dica: Use aspas nos padrões para evitar que o terminal os expanda antes da hora.
    """
    root = _find_project_root(os.getcwd())
    
    if not yes_i_know_what_i_am_doing and not dry_run:
        click.echo(Back.RED + Fore.WHITE + Style.BRIGHT + " !!! AVISO NUCLEAR !!! " + Style.RESET_ALL)
        click.echo(Fore.RED + "Esta operação irá reescrever TODO o histórico do projeto.")
        click.echo(Fore.YELLOW + "Hashes mudarão. 'git push --force' será necessário.")
        
        if not click.confirm(Fore.CYAN + "\nVocê possui um backup físico e deseja prosseguir?"):
            return
    with ExecutionLogger('purge-history', root, ctx.params) as _:
        from .git_systems.git_archivist import GitArchivist
        archivist = GitArchivist(root)
        
        # Converte a tupla para lista para o motor
        success, msg = archivist.nuclear_purge(list(patterns), dry_run)
        
        if success:
            click.echo(Fore.GREEN + Style.BRIGHT + f"\n✔ {msg}")
            if not dry_run:
                click.echo(Fore.CYAN + "\nIMPORTANTE: O git-filter-repo remove o 'origin' por segurança.")
                click.echo(Fore.YELLOW + "Rode: git remote add origin <URL_DO_REPO>")
                click.echo(Fore.YELLOW + "Depois: git push origin main --force")
        else:
            click.echo(Fore.RED + f"\n✘ Falha na Purga: {msg}")