# doxoade/doxoade/commands/pedia.py
"""
Doxoadepédia CLI - Interface de Inteligência Documental (v95.0 Gold).
Orquestrador CLI que delega para o subsistema 'pedia_systems'.
Compliance: MPoT-1 (Facade Pattern), PASC-8.5.
"""
import os
import click
from .pedia_systems.pedia_engine import PediaEngine
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

def _get_engine():
    """Factory para instanciar a Engine com o contexto correto."""
    root = _find_project_root(os.getcwd())
    return PediaEngine(root)

@click.group('pedia', invoke_without_command=True)
@click.pass_context
@click.option('--search', '-s', help='Atalho para busca rápida.')
@click.option('--list', '-l', 'show_list', is_flag=True, help='Lista todo o acervo.')
def pedia(ctx, search, show_list):
    """
    🧠 Doxoadepédia: Base de Conhecimento Central (Thoth).
    Acesse documentação interna, padrões e soluções conhecidas.
    """
    if ctx.invoked_subcommand is not None:
        return
    root = _find_project_root(os.getcwd())
    with ExecutionLogger('pedia', root, ctx.params):
        engine = _get_engine()
        if search:
            engine.search_knowledge(search, limit=10)
        elif show_list:
            engine.list_articles()
        else:
            click.echo(click.get_current_context().get_help())

@pedia.command('read')
@click.argument('topic')
def read_article(topic):
    """Lê um artigo completo pelo nome ou chave."""
    with ExecutionLogger('pedia-read', '.', {'topic': topic}):
        _get_engine().read_article(topic)

@pedia.command('search')
@click.argument('query')
@click.option('--limit', '-n', default=10, help='Limite de resultados.')
def search_cmd(query, limit):
    """Busca semântica no acervo de conhecimento."""
    with ExecutionLogger('pedia-search', '.', {'query': query}):
        _get_engine().search_knowledge(query, limit)

@pedia.command('list')
def list_cmd():
    """Lista todos os artigos disponíveis no índice."""
    with ExecutionLogger('pedia-list', '.', {}):
        _get_engine().list_articles()

@pedia.command('refresh')
def refresh_cmd():
    """Força a reindexação da base de conhecimento (Cache Busting)."""
    with ExecutionLogger('pedia-refresh', '.', {}):
        _get_engine()
        click.echo('✅ Índice de conhecimento recarregado da memória física.')
