# doxoade/doxoade/commands/search.py
"""
Hub de Pesquisa Híbrido Nexus v100.0.
Suporta buscas textuais no código, incidentes, histórico Git e arquivos deletados com exibição rica e defensiva.
"""
import os
# [DOX-UNUSED] import sys
import click
# [DOX-UNUSED] import json
# [DOX-UNUSED] from collections import defaultdict
from doxoade.tools.doxcolors import Fore, Style
# [DOX-UNUSED] from doxoade.database import get_db_connection
from doxoade.commands.search_systems.search_diff import (
    search_git_diffs_pickaxe,
    search_commit_grep,
    search_deleted_files
)

@click.command('search')
@click.argument('query', required=False)
@click.option('--code', '-c', is_flag=True, help="Busca no código/docs")
@click.option('--full', '-f', is_flag=True, help="Exibe a função inteira")
@click.option('--commits', is_flag=True, help="Busca no histórico Git")
@click.option('--here', '-H', is_flag=True, help="Filtra resultados deste diretório")
@click.option('--specify-commit', '-sc', help="Busca código em commit específico")
@click.option('--incidents', '-i', is_flag=True, help="Busca incidentes ativos")
@click.option('--timeline', '-t', is_flag=True, help="Busca na timeline Chronos")
@click.option('--limit', '-n', default=100, type=int, help="Limite de resultados")
@click.option('--deleted', '-d', is_flag=True, help="Busca arquivos deletados na história do Git")
@click.option('--diffs', '-dp', is_flag=True, help="Busca termos dentro dos diffs históricos (Git Pickaxe)")
def search(query, code, full, commits, here, specify_commit, incidents, timeline, limit, deleted, diffs):
    """🧠 Hub de Busca Nexus: Investiga código, histórico, logs e arquivos deletados."""
    if not query:
        click.echo("❌ Forneça um termo de pesquisa.")
        return

    click.secho(f"\n╔═══ Nexus Search: '{query}' ═══╗\n", fg='cyan', bold=True)

    # 1. Caso de Busca de Arquivos Deletados
    if deleted:
        click.secho("[ARQUIVOS DELETADOS NO HISTÓRICO]", fg='magenta', bold=True)
        results = search_deleted_files(query)
        if not results:
            click.echo("  Nenhum arquivo deletado correspondente encontrado.")
            return
        
        for r in results[:limit]:
            status_lbl = "Correspondência por Nome" if r.get('match_by_name') else f"{r.get('occurrences', 0)} ocorrências no corpo"
            click.secho(f"\n 📂 {r.get('file', 'unknown')} [DELETADO]", fg='red', bold=True)
            
            # Acesso defensivo com .get() para prevenir KeyError em cenários parciais
            author = r.get('author', 'unknown')
            date_str = r.get('date', 'unknown')
            summary = r.get('summary', 'No commit message')
            commit_hash = r.get('commit', 'unknown')
            
            click.echo(f"   Autor Exclusão : {Fore.WHITE}{author}{Style.RESET_ALL} | Data: {Fore.WHITE}{date_str}{Style.RESET_ALL}")
            click.echo(f"   Commit Exclusão: {Fore.YELLOW}{commit_hash[:8]}{Style.RESET_ALL} | Mensagem: {Fore.CYAN}“{summary[:75]}”{Style.RESET_ALL}")
            click.echo(f"   Status         : {Fore.CYAN}{status_lbl}{Style.RESET_ALL}")
            
            sample = r.get('sample', {})
            if sample:
                click.echo(f"   {Style.DIM}--- CONTEÚDO ANTES DA EXCLUSÃO ---{Style.RESET_ALL}")
                for line_num, text in sorted(sample.items(), key=lambda x: int(x[0])):
                    color = Fore.YELLOW + Style.BRIGHT if query.lower() in text.lower() else Fore.WHITE + Style.DIM
                    click.echo(f"        {color}{line_num:4} | {text}{Style.RESET_ALL}")
        return

    # 2. Caso de Busca em Commit Específico (Grep histórico)
    if specify_commit:
        click.secho("[COMMIT GREP] Buscando no commit {specify_commit[:8]}...", fg='blue', bold=True)
        results = search_commit_grep(query, specify_commit)
        if not results:
            click.echo("Nenhuma ocorrência encontrada neste commit.")
            return
        for r in results[:limit]:
            click.echo(f"  • {Fore.CYAN}{r['file']}:{r['line']}{Style.RESET_ALL} : {Style.DIM}{r['text']}{Style.RESET_ALL}")
        return

    # 3. Caso de Busca no Histórico de Diffs (Pickaxe)
    if commits or diffs:
        click.secho("[GIT PICKAXE HISTÓRICO]", fg='blue', bold=True)
        results = search_git_diffs_pickaxe(query)
        if not results:
            click.echo("Nenhuma alteração histórica contendo este termo encontrada.")
            return
        for commit in results[:limit]:
            click.echo(f"\n   Commit: {Fore.CYAN}{commit['hash'][:8]}{Fore.WHITE} | {Style.DIM}{commit['summary'][:70]}{Style.RESET_ALL}")
            for match in commit['matches']:
                prefix = f"{Fore.GREEN}+" if match['type'] == 'ADD' else f"{Fore.RED}-"
                color = Fore.GREEN if match['type'] == 'ADD' else Fore.RED
                click.echo(f"      {prefix} {color}{match['content']}{Style.RESET_ALL}")
        return

    # 4. Busca Padrão: Código & Docs (Integração Oficial SearchState)
    click.secho("[Código & Docs]", fg='green', bold=True)
    try:
        from .search_systems.search_state import SearchState
        from .search_systems.search_engine import run_search_engine
        from .search_systems.search_utils import render_search_results
        from doxoade.tools.filesystem import _find_project_root
        
        project_root = _find_project_root(os.getcwd()) or os.getcwd()
        state = SearchState(root=project_root, query=query, limit=limit, is_full_mode=full)
        
        # Mapeamento do dicionário de diretrizes operacionais para o motor padrão do doxoade
        filters = {
            'here': here,
            'commits': commits,
            'run_code': code or not any([incidents, timeline]),
            'run_time': timeline or not any([code, incidents]),
            'run_db': incidents or not any([code, timeline])
        }
        
        run_search_engine(state, filters)
        render_search_results(state)
        
    except ImportError:
        # Fallback local de emergência recursivo caso o motor padrão seja inacessível
        import glob
        files = glob.glob("**/*.py", recursive=True) + glob.glob("**/*.c", recursive=True)
        matches = 0
        for f in files:
            if any(x in f for x in ["venv", ".git", "site-packages"]):
                continue
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as src:
                    for i, line in enumerate(src):
                        if query.lower() in line.lower():
                            matches += 1
                            click.echo(f"  • {Fore.CYAN}{f}:{i+1}{Style.RESET_ALL} : {Style.DIM}{line.strip()}{Style.RESET_ALL}")
                            if matches >= limit:
                                break
            except Exception:
                pass
            if matches >= limit:
                break