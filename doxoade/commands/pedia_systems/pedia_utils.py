# doxoade/doxoade/commands/pedia_systems/pedia_utils.py
"""
Pedia Utils - Renderização Visual (v96.5 Gold).
Foco: Headers tipográficos e listas limpas.
"""
import re
import sys
import click
import textwrap
from doxoade.tools.doxcolors import Fore, Style, Back

def safe_emoji(emoji_char: str, fallback: str) -> str:
    try:
        emoji_char.encode(sys.stdout.encoding or 'ascii')
        return emoji_char
    except UnicodeEncodeError:
        return fallback

class MarkdownRenderer:
    """Renderizador Markdown estilo 'Terminal Gold'."""
    BOLD = re.compile('\\*\\*(.*?)\\*\\*')
    ITALIC = re.compile('\\*(.*?)\\*')
    CODE = re.compile('`(.*?)`')

    def __init__(self):
        self.in_code_block = False

    def render(self, content: str):
        self.in_code_block = False
        click.echo('')
        lines = content.splitlines()
        for i, line in enumerate(lines):
            self._render_line(line, lines, i)
        click.echo('')

    def _render_line(self, line: str, all_lines: list, idx: int):
        stripped = line.strip()
        if stripped.startswith('```'):
            self.in_code_block = not self.in_code_block
            border = Fore.LIGHTBLACK_EX + '─' * 60 + Fore.RESET
            click.echo(border)
            return
        if self.in_code_block:
            click.echo(f'{Fore.LIGHTBLACK_EX}│ {Fore.GREEN}{line}{Fore.RESET}')
            return
        if stripped.startswith('# '):
            title = stripped[2:].strip().upper()
            self._render_h1(title)
            return
        elif stripped.startswith('## '):
            title = stripped[3:].strip()
            self._render_h2(title)
            return
        elif stripped.startswith('### '):
            title = stripped[4:].strip()
            self._render_h3(title)
            return
        if re.match('^[\\-\\*\\•]\\s+', stripped):
            content = re.sub('^[\\-\\*\\•]\\s+', '', stripped)
            formatted = self._apply_inline_formatting(content)
            bullet = safe_emoji('🔹', 'o')
            click.echo(f'  {Fore.CYAN}{bullet} {Fore.WHITE}{formatted}{Style.RESET_ALL}')
            return
        if re.match('^\\d+\\.\\s+', stripped):
            click.echo(f'  {Fore.YELLOW}{stripped}{Style.RESET_ALL}')
            return
        if stripped:
            formatted = self._apply_inline_formatting(stripped)
            wrapped = textwrap.fill(formatted, width=85, replace_whitespace=False)
            click.echo(wrapped)
        else:
            click.echo('')

    def _render_h1(self, text):
        """Header Nível 1: Caixa Sólida / Destaque Máximo."""
        click.echo('')
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}╔{'═' * (len(text) + 4)}╗")
        click.echo(f'║  {Fore.WHITE}{text}  {Fore.CYAN}║')
        click.echo(f"╚{'═' * (len(text) + 4)}╝{Style.RESET_ALL}")

    def _render_h2(self, text):
        """Header Nível 2: Sublinhado e Cor Quente."""
        click.echo(f'\n{Fore.MAGENTA}{Style.BRIGHT}■ {text.upper()}{Style.RESET_ALL}')
        click.echo(f"{Fore.MAGENTA}{'─' * 50}{Style.RESET_ALL}")

    def _render_h3(self, text):
        """Header Nível 3: Texto Simples Colorido."""
        click.echo(f'\n{Fore.YELLOW}{Style.BRIGHT}>>> {text}{Style.RESET_ALL}')

    def _apply_inline_formatting(self, text: str) -> str:
        text = self.BOLD.sub(f'{Fore.WHITE}{Style.BRIGHT}\\1{Style.NORMAL}{Fore.RESET}', text)
        text = self.CODE.sub(f'{Back.BLACK}{Fore.GREEN} \\1 {Style.RESET_ALL}', text)
        text = self.ITALIC.sub(f'{Style.DIM}\\1{Style.NORMAL}', text)
        return text
