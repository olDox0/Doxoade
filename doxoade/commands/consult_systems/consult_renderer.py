# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/consult_renderer.py
"""
☀️ APOLO — Renderização Visual da Documentação.
Responsável por formatar a saída no terminal usando Rich, garantindo 
UI/UX clara, com painéis, sintaxe destacada e cores semânticas.
Blindado contra conflitos de colchetes de código Python no Rich Markup.
"""
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markup import escape
from doxoade.tools.doxcolors import Fore, Style


class ConsultRenderer:
    """Renderizador visual para o terminal (Apolo)."""

    def __init__(self):
        self.console = Console()

    def render_doc(self, term: str, doc_text: str, source: str = None):
        """Renderiza a documentação de um objeto específico com formatação Rich."""
        self.console.rule(f"[bold blue]📖 Doxoade Consult: {term}[/bold blue]")
        self.console.print(Panel(
            escape(doc_text), 
            title=f"[bold cyan]Documentação[/bold cyan]", 
            border_style="green",
            expand=False,
            padding=(1, 2)
        ))
        if source:
            self.console.print(Panel(
                Syntax(source, "python", theme="monokai", line_numbers=True, word_wrap=True),
                title=f"[bold magenta]Código Fonte[/bold magenta]",
                border_style="magenta",
                expand=False,
                padding=(1, 2)
            ))

    def render_search_results(self, keyword: str, results: list):
        """Renderiza os resultados da busca por palavra-chave."""
        self.console.print(f"\n[bold yellow]🔍 Módulos locais relacionados a '{keyword}':[/bold yellow]\n")
        formatted_results = []
        for mod_name, desc in results:
            clean_desc = escape(desc)
            formatted_results.append(f"[bold cyan]{mod_name}[/bold cyan] - [dim]{clean_desc}[/dim]")
        result_text = "\n".join(formatted_results)
        self.console.print(Panel(
            result_text,
            title=f"[bold magenta]📚 Resultados da Busca ({len(results)} encontrados)[/bold magenta]",
            border_style="magenta",
            expand=False,
            padding=(1, 2)
        ))

    def render_error(self, term: str, error_msg: str):
        """Renderiza mensagens de erro de forma clara e instrutiva."""
        clean_msg = escape(error_msg)
        clean_term = escape(term)
        self.console.print(Panel(
            f"[bold red]❌ {clean_msg}[/bold red]\n\n"
            f"[dim]💡 Dicas:[/dim]\n"
            f"[dim]  • Verifique a grafia do módulo (ex: 'os.path', 'json', 'requests')[/dim]\n"
            f"[dim]  • Use 'doxoade consult search {clean_term}' para busca por palavra-chave[/dim]\n"
            f"[dim]  • Use 'doxoade consult keywords' para ver palavras reservadas[/dim]",
            title=f"[bold red]Tópico não encontrado: {clean_term}[/bold red]",
            border_style="red",
            expand=False,
            padding=(1, 2)
        ))

    def render_info(self, title: str, content: str):
        """Renderiza informações gerais (ex: keywords, symbols)."""
        self.console.print(Panel(
            escape(content),
            title=f"[bold cyan]{escape(title)}[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(1, 2)
        ))

    def render_deep_search_results(self, keyword: str, results: list):
        """Renderiza os resultados da busca profunda (HTML Docs) com destaque e salvaguarda de tags."""
        self.console.print(f"\n[bold blue]🔍 Busca profunda (Docs HTML) para '{escape(keyword)}':[/bold blue]\n")
        formatted_results = []
        
        # Sentinelas binárias usadas na consulta FTS5
        MARK_START = "\x02"
        MARK_END = "\x03"

        for path, title, snippet in results:
            # 1. Escapa qualquer colchete ou tag Rich presente naturalmente no texto HTML/código
            safe_title = escape(title)
            safe_snippet = escape(snippet)
            
            # 2. Converte os sentinelas em marcação Rich válida e balanceada
            highlighted_snippet = (
                safe_snippet
                .replace(MARK_START, "[bold yellow on black]")
                .replace(MARK_END, "[/bold yellow on black]")
            )
            
            formatted_results.append(
                f"[bold cyan]📄 {safe_title}[/bold cyan]\n"
                f"[dim]↳ {escape(path)}[/dim]\n"
                f"   {highlighted_snippet}\n"
            )

        result_text = "\n".join(formatted_results)
        self.console.print(Panel(
            result_text,
            title=f"[bold magenta]📚 Resultados Profundos ({len(results)} encontrados)[/bold magenta]",
            border_style="magenta",
            expand=False,
            padding=(1, 2)
        ))
