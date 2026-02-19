# -*- coding: utf-8 -*-
# doxoade/commands/search.py (v90.0 Modular Gold)
import os
import click
from colorama import Fore, Style
# [DOX-UNUSED] from pathlib import Path
from ..shared_tools import ExecutionLogger, _find_project_root
from .search_systems.search_state import SearchState
from .search_systems.search_engine import run_search_engine
from .search_systems.search_utils import render_search_results

@click.command('search')
@click.argument('query', required=False, default="")
@click.option('--code', '-c', is_flag=True, help="Busca no código/docs")
@click.option('--full', '-f', is_flag=True, help="Exibe a função inteira")
@click.option('--commits', is_flag=True, help="Busca no histórico Git")
@click.option('--here', '-H', is_flag=True, help="Filtra resultados deste diretório")
@click.option('--specify-commit', '-sc', help="Busca código em commit específico")
@click.option('--incidents', '-i', is_flag=True, help="Busca incidentes ativos")
@click.option('--timeline', '-t', is_flag=True, help="Busca na timeline Chronos")
@click.option('--limit', '-n', default=20, help="Limite de resultados")
@click.pass_context
def search(ctx, query, **kwargs):
    """🔍 Busca Nexus v4.7.1: Modularidade e Aceleração Vulcano."""
    root = _find_project_root(os.getcwd())
    search_q = query if query else ("%" if kwargs.get('here') else "")
    
    if not search_q and not kwargs.get('here'):
        click.echo(Fore.RED + "Erro: Forneça um termo de busca ou use --here.")
        return

    state = SearchState(root=root, query=search_q, limit=kwargs.get('limit'), is_full_mode=kwargs.get('full'))

    with ExecutionLogger('search', root, ctx.params):
        ctx_tag = f" em {os.path.basename(os.getcwd())}" if kwargs.get('here') else ""
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}╔═══ Nexus Search: '{query}'{ctx_tag} ═══╗{Style.RESET_ALL}")

        # 1. Modo Arqueólogo JIT (Snapshots Históricos)
        if kwargs.get('specify_commit'):
            _handle_historic_search(state, kwargs['specify_commit'])
            return

        # 2. Configuração de Filtros (PASC-8.7)
        filters = kwargs
        is_default = not any([kwargs.get('code'), kwargs.get('commits'), 
                             kwargs.get('incidents'), kwargs.get('timeline')])
        
        filters['run_code'] = kwargs.get('code') or is_default
        filters['run_db'] = kwargs.get('incidents') or is_default or kwargs.get('here')
        filters['run_time'] = kwargs.get('timeline') or is_default or kwargs.get('here')

        # 3. Execução (Buffer-Scan Vulcan se disponível)
        run_search_engine(state, filters)

        # 4. Despacho Visual
        render_search_results(state)

def _handle_historic_search(state, commit):
    from .search_systems.search_utils import get_code_from_commit, extract_block_from_git
    click.echo(f"{Fore.YELLOW}⏳ Consultando snapshot do commit: {commit}...{Style.RESET_ALL}")
    
    raw_results = get_code_from_commit(commit, state.query)
    # [FIX] Respeita o limite -n solicitado pelo usuário
    results = raw_results[:state.limit]
    
    if not results:
        click.echo(f"   {Fore.RED}Nenhum match encontrado no commit {commit}.{Style.RESET_ALL}")
        return

    print(f"{Fore.BLUE}{Style.BRIGHT}\n[ARQUEOLOGIA: COMMIT {commit}]{Style.RESET_ALL}")
    for r in results:
        click.echo(Fore.CYAN + "─" * 65 + Style.RESET_ALL) # DELIMITADOR
        click.echo(f"{Fore.BLUE}[HISTORIC] {r['file']}:{r['line']}{Style.RESET_ALL}")
        
        if state.is_full_mode:
            block = extract_block_from_git(commit, r['file'], r['line'])
            # Renderização com controle de estilo
            click.echo(f"{Style.DIM}{block}{Style.RESET_ALL}")
        else:
            click.echo(f"    > {r['text']}")
    click.echo(Fore.CYAN + "─" * 65 + Style.RESET_ALL)