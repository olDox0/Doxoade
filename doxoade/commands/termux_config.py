# -*- coding: utf-8 -*-
# doxoade/commands/termux_config.py
"""
Comando termux-config.
Arquétipo: Zeus (Orquestrador).
"""
import click

@click.command('termux-config')
def termux_config():
    """Configura o Termux (Teclado, Editor, Atalhos e Splits) para produtividade mobile."""
    from .termux_systems.termux_engine import run_termux_config
    run_termux_config()