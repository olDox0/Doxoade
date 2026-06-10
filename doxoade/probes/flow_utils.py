# doxoade/doxoade/probes/flow_utils.py
import os, sys, time, linecache
from doxoade.tools.doxcolors import Fore, Style

# --- CONSTANTES ---
C_BORDER = '\x1b[90m'
C_RESET = '\x1b[0m'
SEP = f'{C_BORDER}│{C_RESET}'

def should_skip_trace(filename: str) -> bool:
    """Filtra infraestrutura e foca no código do usuário."""
    norm = filename.replace('\\', '/').lower()
    noise = ['<frozen', 'typing.py', 'enum.py', 'importlib', 'linecache.py', 'abc.py']
    if any(x in norm for x in noise): return True
    return False

def render_flow_table(timer):
    """Gera a tabela final de hotspots (Top 15) no terminal."""
    stats = timer.top_lines(limit=15)
    if not stats: return

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🌊 NEXUS FLOW: Tabela de Performance (Top 15){Style.RESET_ALL}")
    print(f"{Fore.WHITE}{'MS TOTAL':>10} | {'LOCALIZAÇÃO':<30} | {'CONTEÚDO'}{Style.RESET_ALL}")
    
    for s in stats:
        file_short = os.path.basename(s['file'])
        t_color = Fore.RED if s['total_ms'] > 10 else Fore.CYAN
        print(f"{t_color}{s['total_ms']:>8.2f}ms {Fore.WHITE}│ {Fore.YELLOW}{file_short}:{s['line']:<25} {Fore.WHITE}│ {s['content'][:60]}{Style.RESET_ALL}")
