# -*- coding: utf-8 -*-
# doxoade/commands/termux_command.py

import click

@click.command("termux-config")
@click.option("--remove", is_flag=True, help="Remove as alterações aplicadas.")
@click.option("--tutorial", is_flag=True, help="Exibe o tutorial.")
def termux_config(remove, tutorial):
    if tutorial:
        from .termux_systems.termux_io import print_tutorial
        print_tutorial()
        return

    from .termux_systems.termux_config import main
    main("remove" if remove else "apply")