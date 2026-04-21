# doxoade/doxoade/commands/pedia_systems/pedia_engine.py
import click
from doxoade.tools.doxcolors import Fore, Style
from .pedia_io import KnowledgeBaseIO
from .pedia_search import PediaSearch
from .pedia_utils import MarkdownRenderer, safe_emoji
from .pedia_json import SemanticJSONRenderer

class PediaEngine:
    """Motor central de Inteligência Documental (Atena/Thoth)."""

    def __init__(self, project_root: str):
        self.io = KnowledgeBaseIO(project_root)
        self.articles = self.io.load_all_knowledge()
        self.searcher = PediaSearch(self.articles)
        self.md_renderer = MarkdownRenderer()
        self.json_renderer = SemanticJSONRenderer()

    def read_article(self, topic: str):
        topic_clean = topic.lower().strip()
        article = self.articles.get(topic_clean)
        if not article:
            results = self.searcher.rank_articles(topic_clean, limit=1)
            if results and results[0]['score'] > 50:
                article = results[0]['article']
                click.echo(f"{Fore.YELLOW}Artigo exato '{topic}' não encontrado. Exibindo o mais próximo: '{article.key}'{Style.RESET_ALL}\n")
        if not article:
            click.echo(f"{Fore.RED}✘ Nenhum artigo encontrado para '{topic}'.{Style.RESET_ALL}")
            return
        self._render_article_header(article)
        if not self.json_renderer.try_render(article.content):
            self.md_renderer.render(article.content)

    def search_knowledge(self, query: str, limit: int):
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}🔍 Buscando por: '{query}'...{Style.RESET_ALL}\n")
        results = self.searcher.rank_articles(query, limit)
        if not results:
            click.echo(f'{Fore.YELLOW}Nenhum resultado relevante encontrado.{Style.RESET_ALL}')
            return
        for res in results:
            art = res['article']
            score = res['score']
            color = Fore.GREEN if score >= 80 else Fore.YELLOW if score >= 40 else Fore.WHITE
            source_icon = safe_emoji('🏛️', '[SYS]') if 'CORE' in art.source else safe_emoji('🏠', '[PRJ]')
            click.echo(f'{color}{source_icon} {art.key:<30} {Style.DIM}| Score: {score:>3} | Cat: {art.category}{Style.RESET_ALL}')
            click.echo(f'   {Fore.WHITE}Title: {art.title}{Style.RESET_ALL}')
            click.echo(f'   {Style.DIM}Source: {art.source}{Style.RESET_ALL}\n')

    def list_articles(self):
        click.echo(f'{Fore.CYAN}{Style.BRIGHT}📚 ACERVO DA DOXOADEPÉDIA ({len(self.articles)} documentos){Style.RESET_ALL}\n')
        grouped = {}
        for art in self.articles.values():
            if art.source not in grouped:
                grouped[art.source] = {}
            if art.category not in grouped[art.source]:
                grouped[art.source][art.category] = []
            grouped[art.source][art.category].append(art)
        source_order = ['DOXOADE CORE', 'local']
        for source in source_order:
            if source not in grouped and source == 'local':
                targets = [k for k in grouped.keys() if 'CORE' not in k]
            elif source in grouped:
                targets = [source]
            else:
                continue
            for src_key in targets:
                display_source = 'DOXOADE CORE (SISTEMA)' if 'CORE' in src_key else 'PROJETO ATUAL (LOCAL)'
                click.echo(f'{Fore.MAGENTA}{Style.BRIGHT}=== {display_source} ==={Style.RESET_ALL}')
                cats = grouped[src_key]
                for cat_name in sorted(cats.keys()):
                    click.echo(f'\n{Fore.YELLOW}📂 {cat_name}:{Style.RESET_ALL}')
                    for art in sorted(cats[cat_name], key=lambda x: x.key):
                        click.echo(f'  • {Fore.CYAN}{art.key:<25} {Fore.WHITE}{art.title}{Style.RESET_ALL}')
                click.echo('')

    def _render_article_header(self, article):
        icon = safe_emoji('🏛️', '') if 'CORE' in article.source else safe_emoji('🏠', '')
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
        click.echo(f'{icon}  {article.title.upper()}')
        click.echo(f'    {Style.DIM}Chave: {article.key} | Categoria: {article.category}')
        click.echo(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
