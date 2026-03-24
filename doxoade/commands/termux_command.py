# -*- coding: utf-8 -*-
# doxoade/commands/termux_command.py

import click

@click.command('termux-config')
@click.option('--tutorial', is_flag=True, help="Exibe o tutorial de uso dos atalhos no Micro e Nano.")
@click.option('--config', is_flag=True, help="Executa a configuração do Termux.")
def termux_config(tutorial, config):
    """Configura o Termux (Teclado, Editor, Atalhos e Splits) para produtividade mobile."""
    if tutorial:
        from .termux_systems.termux_io import print_tutorial
        print_tutorial()
        return
    if config:
        from .termux_systems.termux_config import main
        main()
        return

    # fallback padrão (opinião: isso melhora UX)
    click.echo("⚠️  Nenhuma opção fornecida. Use --config ou --tutorial.")