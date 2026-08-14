# -*- coding: utf-8 -*-
# doxoade/commands/hermes_blacklist_cmd.py
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.blacklist import (
    get_unified_blacklist,
    add_to_blacklist,
    remove_from_blacklist,
    load_persistent_blacklist,
)

@click.group('blacklist')
def blacklist_group():
    """Gerencia a blacklist de módulos do Hermes."""
    pass

@blacklist_group.command('list')
@click.option('--verbose', '-v', is_flag=True, help='Mostra origem (hardcoded vs persistente)')
def blacklist_list(verbose):
    """Lista todos os módulos na blacklist."""
    from doxoade.tools.hermes_systems.blacklist import (
        HARDCODED_BLACKLIST, 
        load_persistent_blacklist
    )
    
    project_root = Path.cwd().resolve()
    unified = get_unified_blacklist(project_root)
    persistent = load_persistent_blacklist(project_root)
    
    click.echo(f"{Fore.CYAN}═══ Hermes Blacklist ═══{Style.RESET_ALL}")
    click.echo(f"Total: {len(unified)} módulos")
    click.echo(f"  Hardcoded: {len(HARDCODED_BLACKLIST)}")
    click.echo(f"  Persistente: {len(persistent)}\n")
    
    if verbose:
        click.echo(f"{Fore.YELLOW}Origem:{Style.RESET_ALL}")
        for module in sorted(unified):
            origin = "persistente" if module in persistent else "hardcoded"
            click.echo(f"  {Fore.YELLOW}•{Style.RESET_ALL} {module} ({origin})")
    else:
        for module in sorted(unified):
            click.echo(f"  {Fore.YELLOW}•{Style.RESET_ALL} {module}")

@blacklist_group.command('add')
@click.argument('module_name')
def blacklist_add(module_name: str):
    """Adiciona módulo à blacklist persistente."""
    project_root = Path.cwd().resolve()
    add_to_blacklist(module_name, project_root)
    click.echo(f"{Fore.GREEN}✔ Adicionado: {module_name}{Style.RESET_ALL}")

@blacklist_group.command('remove')
@click.argument('module_name')
def blacklist_remove(module_name: str):
    """Remove módulo da blacklist persistente."""
    project_root = Path.cwd().resolve()
    remove_from_blacklist(module_name, project_root)
    click.echo(f"{Fore.GREEN}✔ Removido: {module_name}{Style.RESET_ALL}")

@blacklist_group.command('test')
@click.argument('module_name')
def blacklist_test(module_name: str):
    """Testa se um módulo está na blacklist."""
    from doxoade.tools.hermes_systems.blacklist import is_blacklisted
    
    project_root = Path.cwd().resolve()
    result = is_blacklisted(module_name, project_root)
    
    if result:
        click.echo(f"{Fore.GREEN}✔ {module_name} ESTÁ na blacklist{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}✘ {module_name} NÃO está na blacklist{Style.RESET_ALL}")
        
@blacklist_group.command('sync')
def blacklist_sync():
    """Sincroniza a blacklist persistente com os defaults do sistema."""
    from doxoade.tools.hermes_systems.blacklist import sync_blacklist_defaults
    
    project_root = Path.cwd().resolve()
    added = sync_blacklist_defaults(project_root)
    
    if added > 0:
        click.echo(f"{Fore.GREEN}✔ {added} módulos adicionados à blacklist persistente{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.CYAN}✔ Blacklist já está sincronizada{Style.RESET_ALL}")
        
@blacklist_group.command('test-path')
@click.argument('file_path', type=click.Path(exists=True))
def blacklist_test_path(file_path: str):
    """Testa se um arquivo específico está na blacklist."""
    from doxoade.tools.hermes_systems.blacklist import is_path_blacklisted
    
    project_root = Path.cwd().resolve()
    result = is_path_blacklisted(file_path, project_root)
    
    if result:
        click.echo(f"{Fore.GREEN}✔ {file_path} ESTÁ bloqueado pela blacklist{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   Este arquivo será ignorado pelo Hermes e pelo scanner de intelligence.{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.YELLOW}⚠ {file_path} NÃO está bloqueado{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   Este arquivo será processado normalmente.{Style.RESET_ALL}")