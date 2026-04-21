# doxoade/doxoade/commands/rescue_cmd.py
import click
from doxoade.tools.doxcolors import Fore, Style
from .rescue_systems.scavenger_logic import Scavenger

@click.command('rescue')
@click.option('--scavenge', '-s', is_flag=True, help='Minera objetos perdidos no Git.')
@click.option('--backups', '-b', is_flag=True, help='Lista backups do Notepad++.')
@click.option('--deep', '-d', help='Busca por termo específico no histórico fantasma.')
@click.option('--npp', '-n', is_flag=True, help='Busca na pasta oculta de backup do Notepad++.')
@click.pass_context
def rescue(ctx, scavenge, backups, deep, npp):
    """🩺 Protocolo Lázaro: Resgate de material volátil ou perdido."""
    scav = Scavenger('.')
    if deep:
        results = scav.deep_scavenge_reflog(deep)
        if not results:
            click.echo(Fore.RED + 'Nenhum rastro encontrado para este termo.')
            return
        click.echo(f'\n{Fore.GREEN}Rastros encontrados no Reflog:{Style.RESET_ALL}')
        for r in results:
            click.echo(f'  {Fore.CYAN}{r}')
        click.echo(Fore.YELLOW + "\nUse 'git show <hash>' para tentar ver o conteúdo.")
    if npp:
        backups = scav.recover_from_npp_session()
        click.echo(f'\n{Fore.MAGENTA}Recuperação de Sessão Notepad++ (%APPDATA%):{Style.RESET_ALL}')
        for b in backups[:15]:
            click.echo(f"  {Fore.CYAN}{b['time']} {Fore.WHITE}│ {b['name']}")
    if scavenge:
        blobs = scav.find_dangling_blobs()
        if not blobs:
            click.echo(Fore.RED + 'Nenhum fragmento de código órfão encontrado.')
            return
        click.echo(f'\n{Fore.GREEN}Encontrados {len(blobs)} fragmentos no abismo:{Style.RESET_ALL}')
        for i, b in enumerate(blobs):
            click.echo(f"[{i}] {Fore.CYAN}{b['hash']}{Fore.WHITE} ({b['date']})")
            click.echo(f"    > {Style.DIM}{b['preview']}...{Style.RESET_ALL}")
        idx = click.prompt("\nDeseja restaurar algum fragmento? (número ou 'n')", default='n')
        if idx.isdigit() and int(idx) < len(blobs):
            target = blobs[int(idx)]
            fname = click.prompt('Nome do arquivo para salvar (ex: resgate.py)')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(target['full'])
            click.echo(Fore.GREEN + f'✔ Material materializado em {fname}')
    if backups:
        files = scav.scan_npp_backups()
        click.echo(f'\n{Fore.YELLOW}Backups do Notepad++ encontrados:{Style.RESET_ALL}')
        for f in files[:10]:
            click.echo(f"  {Fore.CYAN}{f['date']} {Fore.WHITE}│ {f['name']}")
