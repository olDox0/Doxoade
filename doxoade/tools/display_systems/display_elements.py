# doxoade/doxoade/tools/display_systems/display_elements.py
import click
import os
from doxoade.tools.doxcolors import Fore, Style, Back

def sep(width=85, color=Fore.CYAN, dim=True):
    char = "─"
    style = Style.DIM if dim else ""
    click.echo(f"{color}{style}{char * width}{Style.RESET_ALL}")

def file_panel(file_path):
    """Barra sólida para arquivos."""
    file_name = os.path.basename(file_path)
    click.echo("")
    click.secho(f" 📂 {file_name} ", fg='white', bg='red', bold=True)
    click.secho(f" {Style.DIM}{file_path}{Style.RESET_ALL}")

def badge(severity, category, message):
    """Marcador visual de severidade."""
    icons = {
        'CRITICAL': (Fore.MAGENTA, "☠"),
        'ERROR':    (Fore.RED, "✘"),
        'WARNING':  (Fore.YELLOW, "●"),
        'INFO':     (Fore.CYAN, "ℹ")
    }
    color, icon = icons.get(severity.upper(), (Fore.WHITE, "•"))
    cat_tag = f"[{category}] " if category else ""
    return f"  {color}{icon} {cat_tag}{Fore.WHITE}{Style.BRIGHT}{message}{Style.RESET_ALL}"

def code_block(file_path, target_line, snippet=None):
    """Exibe o código com recuperação automática se estiver vazio."""
    from doxoade.tools.analysis import _get_code_snippet
    
    # Facilitude: Se o snippet não veio no finding (caso do cache), buscamos agora
    if not snippet:
        snippet = _get_code_snippet(file_path, target_line)
    
    if not snippet: return

    click.echo(f"     {Fore.YELLOW}{Back.BLUE} CODE {Style.RESET_ALL}")
    
    try:
        sorted_keys = sorted([int(k) for k in snippet.keys()])
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] code_block: {e}")
        return

    for ln in sorted_keys:
        text = snippet.get(str(ln)) or snippet.get(ln)
        is_target = ln == target_line
        
        prefix = " >> " if is_target else "    "
        line_color = Fore.YELLOW if is_target else Style.DIM
        content_color = Fore.WHITE if is_target else Style.DIM
        
        click.echo(f"     {line_color}{prefix}{ln:4} | {content_color}{text}{Style.RESET_ALL}")

def diff_view(broken, fixed):
    """Exibe o Delta (Antes/Depois) com cores táticas de diff."""
    # Remove espaços extras para focar no código
    b = broken.strip() if broken else "???"
    f = fixed.strip() if fixed else "???"
    
    click.echo(f"     {Fore.RED}{Style.DIM} [-] ATUAL  : {b}{Style.RESET_ALL}")
    click.echo(f"     {Fore.GREEN}{Style.BRIGHT} [+] FIX    : {f}{Style.RESET_ALL}")

def remedy(text, is_historical=True, fixed_content=None, original_content=None, line_num=0):
    """Sugestão tática limpa com prévia integrada."""
    label = "💡 ACERVO" if is_historical else "🔧 AÇÃO"
    color = Fore.GREEN if is_historical else Fore.YELLOW
    click.echo(f"     {color}{Style.BRIGHT}{label}:{Style.RESET_ALL} {Fore.WHITE}{text}{Style.RESET_ALL}")
    
    # Refinamento: Exibição elegante da prévia na UI normal
    if fixed_content:
        click.echo(f"     {Fore.CYAN}{Style.DIM}PREVIA:{Style.RESET_ALL}")
        if original_content:
            click.echo(f"      {Fore.RED}-{line_num:4} | {original_content.strip()}{Style.RESET_ALL}")
        click.echo(f"      {Fore.GREEN}+{line_num:4} | {fixed_content.strip()}{Style.RESET_ALL}")