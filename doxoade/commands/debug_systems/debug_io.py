# -*- coding: utf-8 -*-
"""
Debug IO v2.2 - Interface Forense (PASC-10).
Renderização de autópsia, perfil profundo, hotspots e call chain.
"""
import os
import re
# [DOX-UNUSED] import linecache
from click import echo
from doxoade.tools.doxcolors import Fore, Style


# ─── HELPERS DE DISPLAY ──────────────────────────────────────────────────────

def _bar(value: float, max_val: float, width: int = 10, color: str = Fore.GREEN) -> str:
    pct  = min(1.0, value / max_val) if max_val > 0 else 0
    fill = int(width * pct)
    return f"{color}{'█' * fill}{Style.DIM}{'░' * (width - fill)}{Style.RESET_ALL}"


def _trunc(s: str, n: int) -> str:
    """Trunca pela esquerda mantendo o sufixo mais informativo."""
    if len(s) <= n:
        return s.ljust(n)
    # Prefere exibir ...final.py:N em vez de inicio_...
    return ('…' + s[-(n - 1):]).ljust(n)


def _short_path(fname: str) -> str:
    norm = fname.replace('\\', '/')
    for marker in ('site-packages/', 'dist-packages/'):
        idx = norm.find(marker)
        if idx >= 0:
            after = norm[idx + len(marker):]
            parts = after.split('/')
            return '/'.join(parts[:2]) if len(parts) >= 2 else after
    return norm.split('/')[-1]


# ─── SYNTAX HIGHLIGHT ────────────────────────────────────────────────────────

_RE_DEF     = re.compile(r'^(\s*)(async\s+)?(def\s+)(\w+)')
_RE_CLASS   = re.compile(r'^(\s*)(class\s+)(\w+)')
_RE_IMPORT  = re.compile(r'^(\s*)(from\s+\S+\s+import\s+|import\s+)')
_RE_RETURN  = re.compile(r'^(\s*)(return\b)')
_RE_COMMENT = re.compile(r'^(\s*)(#.*)')


def _colorize(text: str) -> str:
    m = _RE_COMMENT.match(text)
    if m: return f"{m.group(1)}{Style.DIM}{Fore.WHITE}{m.group(2)}{Style.RESET_ALL}"
    m = _RE_DEF.match(text)
    if m:
        return (f"{m.group(1)}{Fore.CYAN}{m.group(2) or ''}{m.group(3)}{Style.RESET_ALL}"
                f"{Style.BRIGHT}{Fore.GREEN}{m.group(4)}{Style.RESET_ALL}"
                f"{Style.DIM}{text[m.end():]}{Style.RESET_ALL}")
    m = _RE_CLASS.match(text)
    if m:
        return (f"{m.group(1)}{Fore.CYAN}{m.group(2)}{Style.RESET_ALL}"
                f"{Style.BRIGHT}{Fore.YELLOW}{m.group(3)}{Style.RESET_ALL}"
                f"{Style.DIM}{text[m.end():]}{Style.RESET_ALL}")
    m = _RE_IMPORT.match(text)
    if m:
        return (f"{m.group(1)}{Fore.BLUE}{m.group(2)}{Style.RESET_ALL}"
                f"{Style.DIM}{text[m.end():]}{Style.RESET_ALL}")
    m = _RE_RETURN.match(text)
    if m:
        return (f"{m.group(1)}{Fore.MAGENTA}{m.group(2)}{Style.RESET_ALL}"
                f"{Style.DIM}{text[m.end():]}{Style.RESET_ALL}")
    return f"{Style.DIM}{text}{Style.RESET_ALL}"


# ─── HEADER / CRASH ──────────────────────────────────────────────────────────

def print_debug_header(script: str, mode: str = "DEBUG"):
    color = Fore.CYAN if mode == "VIGILÂNCIA" else Fore.BLUE
    echo(color + Style.BRIGHT + f"🔍 [ {mode} ] {Fore.WHITE}Analisando: {os.path.basename(script)}\n")


def report_crash(data: dict, script: str):
    echo(f"\n{Fore.RED}{Style.BRIGHT}🚨[ CRASH DETECTADO ]")
    echo(f"{Fore.RED}Erro: {data.get('error', 'Erro desconhecido')}")
    echo(f"{Fore.YELLOW}Local: L{data.get('line', '??')} em {os.path.basename(script)}")
    render_variable_table(data.get('variables'))
    echo(Fore.RED + "\n--- TRACEBACK ---")
    echo(data.get('traceback', 'Nenhum rastro disponível.'))


# ─── TABELA DE VARIÁVEIS ─────────────────────────────────────────────────────

def render_variable_table(variables: dict):
    if not variables:
        return
    echo(Fore.CYAN + "\n[ ESTADO DAS VARIÁVEIS ]")
    for k, v in variables.items():
        val = str(v).replace('\n', ' ')
        if len(val) > 70:
            val = val[:67] + "..."
        echo(f"   {Fore.BLUE}{k:<18} {Fore.WHITE}│ {Style.DIM}{val}")


# ─── HOTSPOT DE LINHAS ───────────────────────────────────────────────────────

# Larguras fixas das colunas — definidas uma vez para header e rows ficarem alinhados
_COL_LOC   = 36   # arquivo:linha  (trunca pela esquerda se necessário)
_COL_BAR   = 10   # blocos █
_COL_TOT   = 10   # "8291.76ms"
_COL_HITS  =  7   # "  2362x"
_COL_HIT   = 10   # "   3.296ms"


def render_line_hotspots(lines: list, total_ms: float):
    """
    Tabela de linhas mais lentas com colunas de largura fixa.

    Colunas: ARQUIVO:LINHA | BAR | TOTAL | HITS | MS/HIT | CÓDIGO
    """
    if not lines:
        return

    SEP = f"{Style.DIM}│{Style.RESET_ALL}"

    echo(f"\n   {Fore.RED}🔥 Hot Lines por Tempo de Execução:{Style.RESET_ALL}")

    # ── Header ───────────────────────────────────────────────────────────────
    h_loc  = 'ARQUIVO:LINHA'.ljust(_COL_LOC)
    h_bar  = 'BAR'.center(_COL_BAR)
    h_tot  = 'TOTAL'.rjust(_COL_TOT)
    h_hits = 'HITS'.rjust(_COL_HITS)
    h_hit  = 'MS/HIT'.rjust(_COL_HIT)
    echo(
        f"   {Style.BRIGHT}"
        f"{h_loc} {h_bar}  {h_tot} {h_hits} {h_hit}  CÓDIGO"
        f"{Style.RESET_ALL}"
    )
    echo(f"   {Style.DIM}{'─' * (_COL_LOC + _COL_BAR + _COL_TOT + _COL_HITS + _COL_HIT + 12)}{Style.RESET_ALL}")

    max_ms = lines[0]['total_ms'] if lines else 1

    for item in lines[:15]:
        short  = _short_path(item['file'])
        label  = _trunc(f"{short}:{item['line']}", _COL_LOC)
        bar    = _bar(item['total_ms'], max_ms, _COL_BAR, Fore.RED)
        tot    = f"{item['total_ms']:>8.2f}ms"
        hits   = f"{item['hits']:>5}x"
        phit   = f"{item['per_hit_ms']:>8.3f}ms"
        code   = item['content'][:40] if item['content'] else ''
        colored = _colorize(code)

        echo(
            f"   {Fore.YELLOW}{label}{Style.RESET_ALL} "
            f"{bar}  "
            f"{Fore.WHITE}{tot}{Style.RESET_ALL} "
            f"{Style.DIM}{hits}{Style.RESET_ALL} "
            f"{Style.DIM}{phit}{Style.RESET_ALL}  "
            f"{colored}"
        )


# ─── HOTSPOT DE FUNÇÕES ───────────────────────────────────────────────────────

_COL_FN   = 22   # nome da função
_COL_FILE = 22   # arquivo:linha
_COL_CALL =  7   # calls
_COL_TT   =  9   # total ms
_COL_PC   =  9   # ms/call
_COL_CUM  =  9   # cum ms


def render_function_hotspots(functions: list):
    """
    Tabela de funções ordenadas por tempo cumulativo com colunas fixas.
    """
    if not functions:
        return

    echo(f"\n   {Fore.MAGENTA}⚡ Hot Functions (cProfile):{Style.RESET_ALL}")

    h_fn   = 'FUNÇÃO'.ljust(_COL_FN)
    h_file = 'ARQUIVO'.ljust(_COL_FILE)
    h_call = 'CALLS'.rjust(_COL_CALL)
    h_tt   = 'TOTAL'.rjust(_COL_TT)
    h_pc   = 'MS/CALL'.rjust(_COL_PC)
    h_cum  = 'CUM'.rjust(_COL_CUM)
    echo(
        f"   {Style.BRIGHT}"
        f"{'BAR':^6} {h_fn} {h_file} {h_call} {h_tt} {h_pc} {h_cum}"
        f"{Style.RESET_ALL}"
    )
    echo(f"   {Style.DIM}{'─' * (_COL_FN + _COL_FILE + _COL_CALL + _COL_TT + _COL_PC + _COL_CUM + 14)}{Style.RESET_ALL}")

    max_cum = functions[0]['cum_ms'] if functions else 1

    for fn in functions[:15]:
        short  = _short_path(fn['file'])
        loc    = _trunc(f"{short}:{fn['lineno']}", _COL_FILE)
        bar    = _bar(fn['cum_ms'], max_cum, 6, Fore.MAGENTA)
        name   = _trunc(fn['name'], _COL_FN)
        calls  = f"{fn['calls']:>{_COL_CALL}}"
        tt     = f"{fn['total_ms']:>{_COL_TT - 2}.2f}ms"
        pc     = f"{fn['per_call_ms']:>{_COL_PC - 2}.3f}ms"
        cum    = f"{fn['cum_ms']:>{_COL_CUM - 2}.2f}ms"

        echo(
            f"   {bar} "
            f"{Fore.CYAN}{name}{Style.RESET_ALL} "
            f"{Style.DIM}{loc}{Style.RESET_ALL} "
            f"{calls}  "
            f"{Fore.YELLOW}{tt}{Style.RESET_ALL}  "
            f"{Style.DIM}{pc}{Style.RESET_ALL}  "
            f"{Fore.RED}{cum}{Style.RESET_ALL}"
        )


# ─── MEMÓRIA ─────────────────────────────────────────────────────────────────

_COL_MEM_LOC  = 32
_COL_MEM_SIZE = 9
_COL_MEM_CNT  = 7


def render_memory_report(memory: dict):
    if not memory:
        return

    peak_mb    = memory.get('peak_mb', 0)
    top_allocs = memory.get('top_allocs', [])

    echo(f"\n   {Fore.BLUE}🧠 Memória (tracemalloc):{Style.RESET_ALL}")
    echo(
        f"   {Style.BRIGHT}Pico de memória:{Style.RESET_ALL} "
        f"{Fore.YELLOW}{peak_mb:.3f} MB{Style.RESET_ALL}"
    )

    if not top_allocs:
        return

    echo(f"\n   {Style.DIM}Top Alocações por Linha:{Style.RESET_ALL}")

    h_loc  = 'ARQUIVO:LINHA'.ljust(_COL_MEM_LOC)
    h_bar  = 'BAR'.center(10)
    h_size = 'TAMANHO'.rjust(_COL_MEM_SIZE)
    h_cnt  = 'OBJETOS'.rjust(_COL_MEM_CNT)
    echo(f"   {Style.BRIGHT}{h_loc} {h_bar}  {h_size} {h_cnt}  CÓDIGO{Style.RESET_ALL}")
    echo(f"   {Style.DIM}{'─' * 80}{Style.RESET_ALL}")

    max_kb = top_allocs[0]['size_kb'] if top_allocs else 1
    for alloc in top_allocs[:10]:
        short  = _short_path(alloc['file'])
        label  = _trunc(f"{short}:{alloc['line']}", _COL_MEM_LOC)
        bar    = _bar(alloc['size_kb'], max_kb, 10, Fore.BLUE)
        size   = f"{alloc['size_kb']:>{_COL_MEM_SIZE - 2}.1f}KB"
        cnt    = f"{alloc['count']:>{_COL_MEM_CNT}}x"
        code   = alloc['content'][:35] if alloc['content'] else ''
        colored = _colorize(code)
        echo(
            f"   {Fore.CYAN}{label}{Style.RESET_ALL} "
            f"{bar}  "
            f"{Fore.WHITE}{size}{Style.RESET_ALL} "
            f"{Style.DIM}{cnt}{Style.RESET_ALL}  "
            f"{colored}"
        )


# ─── DIAGNÓSTICO FINAL ───────────────────────────────────────────────────────

_IO_PAT     = re.compile(r'\b(open|read|write|recv|send|readline|flush|seek|connect|accept)\b')
_LOOP_PAT   = re.compile(r'\b(for|while)\b')
_IMPORT_PAT = re.compile(r'^\s*(import|from)\b')
_CALL_PAT   = re.compile(r'\w+\s*\(')


def render_bottleneck_diagnosis(lines: list, functions: list, total_ms: float):
    if not lines and not functions:
        return

    echo(f"\n   {Fore.RED}🔴 Diagnóstico de Gargalo:{Style.RESET_ALL}")
    echo(f"   {Style.DIM}{'─' * 60}{Style.RESET_ALL}")

    for item in lines[:5]:
        c = item['content']
        if not c:
            continue
        if _IMPORT_PAT.match(c):
            kind, tip, color = 'IMPORT-BOUND', 'Mova este import para o topo do módulo, se não for otimização.', Fore.YELLOW
        elif _IO_PAT.search(c):
            kind, tip, color = 'IO-BOUND', 'Considere async I/O, buffer maior ou cache de resultado.', Fore.CYAN
        elif _LOOP_PAT.search(c):
            kind, tip, color = 'CPU-BOUND (loop)', 'Candidate a Vulcan/Cython ou vetorização com numpy.', Fore.RED
        elif item['hits'] > 500 and _CALL_PAT.search(c):
            kind, tip, color = 'CALL-BOUND', 'Alta frequência de chamada. Considere memoize/lru_cache.', Fore.MAGENTA
        else:
            kind, tip, color = 'CPU-BOUND', 'Hotspot puro de CPU. Candidate a Vulcan/Cython.', Fore.RED

        short = _short_path(item['file'])
        pct   = round(item['total_ms'] / max(total_ms, 0.001) * 100, 1)

        echo(
            f"\n   {color}{Style.BRIGHT}[{kind}]{Style.RESET_ALL}"
            f"  {Style.DIM}{short}:{item['line']}{Style.RESET_ALL}"
            f"  {Fore.YELLOW}{pct}% do tempo total{Style.RESET_ALL}"
        )
        echo(f"   {Style.DIM}código: {c}{Style.RESET_ALL}")
        echo(f"   {Fore.GREEN}💡 {tip}{Style.RESET_ALL}")

    echo(f"\n   {Style.DIM}{'─' * 60}{Style.RESET_ALL}")


# ─── RELATÓRIO COMPLETO DE PERFIL ────────────────────────────────────────────

def render_profile_report(data: dict, script: str):
    profile  = data.get('profile', {})
    if not profile:
        echo(f"   {Style.DIM}(sem dados de perfil){Style.RESET_ALL}")
        return

    total_ms  = profile.get('total_ms', 0)
    lines     = profile.get('lines', [])
    functions = profile.get('functions', [])
    memory    = profile.get('memory', {})

    # ── Sumário ───────────────────────────────────────────────────────────────
    echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}=== 🔬 PERFIL PROFUNDO: "
        f"{os.path.basename(script)} ==={Style.RESET_ALL}"
    )
    echo(
        f"   {Style.BRIGHT}Tempo total:{Style.RESET_ALL} "
        f"{Fore.YELLOW}{total_ms:.2f} ms{Style.RESET_ALL}"
        f"  {Style.DIM}│  pico RAM: "
        f"{memory.get('peak_mb', 0):.3f} MB{Style.RESET_ALL}"
    )

    if data.get('status') == 'error':
        report_crash(data, script)

    render_line_hotspots(lines, total_ms)
    render_function_hotspots(functions)
    render_memory_report(memory)
    render_bottleneck_diagnosis(lines, functions, total_ms)

    if data.get('variables'):
        render_variable_table(data['variables'])