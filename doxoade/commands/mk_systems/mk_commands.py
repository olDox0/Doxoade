# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_commands.py
import click
import os
from doxoade.tools.doxcolors import Fore, Style
from .mk_engine import MkEngine
from ...shared_tools import _find_project_root
def register_mk_options(f):
    """Decorator para centralizar opções do MK."""
    f = click.option('--architecture', '-a', type=click.Path(exists=True), 
                     help="Cria estrutura baseada em arquivo de arquitetura.")(f)
    f = click.option('--learning', '-l', type=click.Path(exists=True), 
                     help="Cria estrutura baseada em arquivo de aprendizado (Gênese).")(f)
    return f
def execute_mk_logic(base_path, items, architecture, tree):
    engine = MkEngine(base_path)
    root = _find_project_root(base_path)
    
    if tree:
        folder_name = os.path.basename(os.path.abspath(base_path))
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TREE] Topologia de '{folder_name}' ---")
        # FIX: Passando o root que o engine agora exige
        for line in engine.render_tree(base_path, root):
            click.echo(line)
        click.echo(Fore.CYAN + "------------------------------------------")
        return
    if architecture:
        click.echo(Fore.CYAN + f"--- [MK-ARCH] Construindo a partir de: {architecture} ---")
        for path, kind in engine.parse_architecture_file(architecture):
            click.echo(Fore.GREEN + f"[OK] {kind:<10}: {path}")
        return
    if items:
        click.echo(Fore.CYAN + f"--- [MK-ITEMS] Criando itens em: {base_path} ---")
        for item in items:
            for expanded in engine._expand_and_create(0, item): # Método interno simplificado
                click.echo(Fore.GREEN + f"[OK] Criado: {expanded}")