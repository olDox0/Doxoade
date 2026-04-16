# doxoade/doxoade/commands/termux_command.py
import click

@click.command('termux-config')
@click.option('--tutorial', is_flag=True, help='Exibe o tutorial.')
@click.option('--remove', is_flag=True, help='Remove as alterações aplicadas.')
@click.option('--reset', is_flag=True, help='Remove e limpa backups/estado para reaplicar do zero.')
def termux_config(tutorial, remove, reset):
    if tutorial:
        from .termux_systems.termux_io import print_tutorial
        print_tutorial()
        return
    from .termux_systems.termux_config import main
    if reset:
        main('reset')
    elif remove:
        main('remove')
    else:
        main('apply')