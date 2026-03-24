# -*- coding: utf-8 -*-
# doxoade/commands/termux_config.py
"""
Comando termux-config.
Arquétipo: Zeus (Orquestrador).
"""
import click

@click.command('termux-config')
@click.option('--tutorial', is_flag=True, help="Exibe o tutorial de uso dos atalhos no Micro e Nano.")
def termux_config(tutorial):
    """Configura o Termux (Teclado, Editor, Atalhos e Splits) para produtividade mobile."""
    if tutorial:
        from .termux_systems.termux_io import print_tutorial
        print_tutorial()
    else:
        from .termux_systems.termux_engine import run_termux_config
        run_termux_config()