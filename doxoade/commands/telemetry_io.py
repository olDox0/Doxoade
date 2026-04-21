# doxoade/doxoade/commands/telemetry_io.py
"""
Telemetry IO v3.9 - Interface Nexus Gold.
Exibição de I/O, Memória, Fluxo e Contexto com Syntax Highlight.
"""
import os
import re
import linecache
from click import echo
from doxoade.tools.doxcolors import Fore, Style

def draw_bar(value, max_val, width=10, color=Fore.GREEN):
    percent = min(1.0, value / max_val) if max_val > 0 else 0
    fill = int(width * percent)
    return f"{color}{'█' * fill}{Style.DIM}{'░' * (width - fill)}{Style.RESET_ALL}"

def render_resource_line(label, val, formatted_val, bar_color, max_ref, status):
    bar = draw_bar(val, max_ref, 10, bar_color)
    echo(f'   {Style.BRIGHT}{label:<10}{Style.NORMAL} {bar} {formatted_val:>10} │ {status}')

def render_disk_detail(read_mb, write_mb, status):
    from .telemetry_utils import format_bytes
    total = read_mb + write_mb
    bar = draw_bar(total, 50, 10, Fore.BLUE)
    r_str = f'{Fore.CYAN}R:{format_bytes(read_mb)}{Fore.RESET}'
    w_str = f'{Fore.YELLOW}W:{format_bytes(write_mb)}{Fore.RESET}'
    echo(f"   {Style.BRIGHT}{'DISK I/O':<10}{Style.NORMAL} {bar} {r_str} / {w_str} │ {status}")

def _lib_short(fname: str) -> str:
    norm = fname.replace('\\', '/')
    for marker in ('site-packages/', 'dist-packages/'):
        idx = norm.find(marker)
        if idx >= 0:
            after = norm[idx + len(marker):]
            parts = after.split('/')
            return '/'.join(parts[:2]) if len(parts) >= 2 else after
    return norm.split('/')[-1]

def _proj_short(fname: str) -> str:
    return fname.replace('\\', '/').split('/')[-1]

def _short(fname: str, layer: str) -> str:
    return _lib_short(fname) if layer == 'lib' else _proj_short(fname)
_RE_DEF = re.compile('^(\\s*)(async\\s+)?(def\\s+)(\\w+)')
_RE_CLASS = re.compile('^(\\s*)(class\\s+)(\\w+)')
_RE_IMPORT = re.compile('^(\\s*)(from\\s+\\S+\\s+import\\s+|import\\s+)')
_RE_RETURN = re.compile('^(\\s*)(return\\b)')
_RE_DECO = re.compile('^(\\s*)(@\\w+)')
_RE_COMMENT = re.compile('^(\\s*)(#.*)')
_RE_SELF = re.compile('\\bself\\b')
_RE_STR_SQ = re.compile("'[^']*'")
_RE_STR_DQ = re.compile('"[^"]*"')

def _colorize_line(text: str) -> str:
    """
    Aplica cores simples a uma linha de código Python para o terminal.
    Prioridade: comentário > decorador > def > class > import > return > inline.
    Retorna a string já colorida (com escape codes).
    """
    m = _RE_COMMENT.match(text)
    if m:
        return f'{m.group(1)}{Style.DIM}{Fore.WHITE}{m.group(2)}{Style.RESET_ALL}'
    m = _RE_DECO.match(text)
    if m:
        rest = text[m.end():]
        return f'{m.group(1)}{Fore.YELLOW}{m.group(2)}{Style.RESET_ALL}{Style.DIM}{rest}{Style.RESET_ALL}'
    m = _RE_DEF.match(text)
    if m:
        indent = m.group(1)
        async_kw = m.group(2) or ''
        def_kw = m.group(3)
        fname = m.group(4)
        rest = text[m.end():]
        return f'{indent}{Fore.CYAN}{async_kw}{def_kw}{Style.RESET_ALL}{Style.BRIGHT}{Fore.GREEN}{fname}{Style.RESET_ALL}{Style.DIM}{rest}{Style.RESET_ALL}'
    m = _RE_CLASS.match(text)
    if m:
        indent = m.group(1)
        class_kw = m.group(2)
        cname = m.group(3)
        rest = text[m.end():]
        return f'{indent}{Fore.CYAN}{class_kw}{Style.RESET_ALL}{Style.BRIGHT}{Fore.YELLOW}{cname}{Style.RESET_ALL}{Style.DIM}{rest}{Style.RESET_ALL}'
    m = _RE_IMPORT.match(text)
    if m:
        indent = m.group(1)
        kw_part = m.group(2)
        rest = text[m.end():]
        return f'{indent}{Fore.BLUE}{kw_part}{Style.RESET_ALL}{Style.DIM}{rest}{Style.RESET_ALL}'
    m = _RE_RETURN.match(text)
    if m:
        indent = m.group(1)
        kw = m.group(2)
        rest = text[m.end():]
        return f'{indent}{Fore.MAGENTA}{kw}{Style.RESET_ALL}{Style.DIM}{rest}{Style.RESET_ALL}'
    return f'{Style.DIM}{text}{Style.RESET_ALL}'

def _colorize_hot_line(text: str) -> str:
    """
    Destaque especial para a linha quente: texto branco brilhante,
    keywords em amarelo, strings em verde.
    """
    out = text
    out = _RE_STR_SQ.sub(lambda m: f'{Fore.GREEN}{m.group()}{Fore.WHITE}', out)
    out = _RE_STR_DQ.sub(lambda m: f'{Fore.GREEN}{m.group()}{Fore.WHITE}', out)
    out = _RE_SELF.sub(f'{Fore.CYAN}self{Fore.WHITE}', out)
    return f'{Style.BRIGHT}{Fore.WHITE}{out}{Style.RESET_ALL}'

def render_hot_lines(line_data):
    if not line_data:
        return
    echo(f'     {Fore.RED}🔥 Hot Lines (Gargalos):{Style.RESET_ALL}')
    for item in line_data[:6]:
        fname, lineno, hits = (item['file'], item['line'], item['hits'])
        abs_fname = os.path.abspath(fname)
        content = linecache.getline(abs_fname, lineno).strip()
        echo(f'       {Fore.YELLOW}{fname}:{lineno:<4}{Style.RESET_ALL} ({hits:>2} hits) > {Style.DIM}{content}{Style.RESET_ALL}')

def render_lib_hot_lines(line_data):
    if not line_data:
        return
    echo(f'     {Fore.BLUE}📦 Hot Lines (Libs):{Style.RESET_ALL}')
    for item in line_data[:6]:
        fname, lineno, hits = (item['file'], item['line'], item['hits'])
        abs_fname = os.path.abspath(fname)
        content = linecache.getline(abs_fname, lineno).strip()
        short = _lib_short(fname)
        echo(f'       {Fore.CYAN}{short}:{lineno:<4}{Style.RESET_ALL} ({hits:>2} hits) > {Style.DIM}{content}{Style.RESET_ALL}')

def _read_context(abs_fname: str, lineno: int, before: int, after: int):
    """
    Lê linhas de contexto ao redor de lineno.
    Retorna (prev_lines, hot_text, next_lines) onde cada item é (n, text).
    Linhas completamente em branco são puladas no contexto, mas nunca
    na hot-line em si.
    """
    prev_lines = []
    for i in range(max(1, lineno - before), lineno):
        text = linecache.getline(abs_fname, i).rstrip()
        if text.strip():
            prev_lines.append((i, text))
    hot_text = linecache.getline(abs_fname, lineno).rstrip()
    next_lines = []
    after_count = max(1, after)
    for i in range(lineno + 1, lineno + after_count + 1):
        text = linecache.getline(abs_fname, i).rstrip()
        if text or not next_lines:
            if text.strip():
                next_lines.append((i, text))
        if len(next_lines) >= after_count:
            break
    return (prev_lines, hot_text, next_lines)

def _render_predecessor_block(fname: str, lineno: int, hits: int, layer: str, indent: str, context_before: int=3, context_after: int=2):
    """
    Exibe o bloco de contexto de uma entrada do caminho crítico.

    Layout:
        indent  ┌─ contexto · short.py:N  (função pai se encontrada)
        indent  │  N-3 │ linha anterior  ← colorida por keyword
        indent  │  N-2 │ linha anterior
        indent  │  N-1 │ linha anterior
        indent  │
        indent  ▶  short.py:N  ◄ NNN hits
        indent     N   │ HOT LINE  ← highlight especial
        indent  │
        indent  │  N+1 │ linha posterior  ← dim
        indent  │  N+2 │ linha posterior
        indent  └────────────────────────

    O bloco "depois" mostra o que a hot-line retorna/propaga,
    ajudando a entender o fluxo de saída do gargalo.
    """
    abs_f = os.path.abspath(fname)
    short = _short(fname, layer)
    color = Fore.GREEN if layer == 'proj' else Fore.BLUE
    prev_lines, hot_text, next_lines = _read_context(abs_f, lineno, context_before, context_after)
    parent_fn = None
    for _, text in reversed(prev_lines):
        m = _RE_DEF.match(text) or _RE_CLASS.match(text)
        if m:
            parent_fn = m.group(0).strip()
            break
    parent_hint = f'  {Style.DIM}← {parent_fn}{Style.RESET_ALL}' if parent_fn else ''
    echo(f'{indent}{Style.DIM}┌─ contexto · {color}{short}:{lineno}{Style.RESET_ALL}{parent_hint}')
    for i, text in prev_lines:
        colored = _colorize_line(text)
        echo(f'{indent}{Style.DIM}│  {i:4} │{Style.RESET_ALL} {colored}')
    echo(f'{indent}{Style.DIM}│{Style.RESET_ALL}')
    echo(f'{indent}{color}▶  {short}:{lineno}{Style.RESET_ALL}  {Style.BRIGHT}{Fore.RED}◄ {hits:,} hits{Style.RESET_ALL}')
    hot_colored = _colorize_hot_line(hot_text)
    echo(f'{indent}   {Style.BRIGHT}{color}{lineno:4} │{Style.RESET_ALL} {hot_colored}')
    if next_lines:
        echo(f'{indent}{Style.DIM}│{Style.RESET_ALL}')
        for i, text in next_lines:
            colored = _colorize_line(text)
            echo(f'{indent}{Style.DIM}│  {i:4} │{Style.RESET_ALL} {colored}')
    echo(f"{indent}{Style.DIM}└{'─' * 48}{Style.RESET_ALL}")

def render_flow_map(flow_data: dict, io_read_mb: float=0.0, io_write_mb: float=0.0):
    from .telemetry_utils import bottleneck_score, format_bytes
    proj = flow_data.get('proj', {})
    libs = flow_data.get('libs', {})
    total_hits = flow_data.get('total_hits', 1) or 1
    BOX_W = 52
    SEP = '─' * BOX_W
    echo(f'\n   {Fore.CYAN}🔀 Fluxo de Dados entre Arquivos:{Style.RESET_ALL}')
    if proj:
        echo(f'   {Style.DIM}┌─ PROJETO {SEP[:BOX_W - 10]}┐{Style.RESET_ALL}')
        for fname, stat in sorted(proj.items(), key=lambda x: x[1]['hits'], reverse=True)[:5]:
            bar = draw_bar(stat['hits'], total_hits, 10, Fore.GREEN)
            short = _proj_short(fname)
            score = bottleneck_score(stat)
            echo(f"   {Style.DIM}│{Style.RESET_ALL}  {Fore.GREEN}{short:<20}{Style.RESET_ALL} {bar} {stat['hits']:>5} hits  {Style.DIM}score:{score:.0f}{Style.RESET_ALL}")
        echo(f'   {Style.DIM}└{SEP}┘{Style.RESET_ALL}')
    if proj and libs:
        io_label = ''
        if io_read_mb > 0 or io_write_mb > 0:
            io_label = f'  {Style.DIM}(I/O  {Fore.CYAN}R:{format_bytes(io_read_mb)}{Style.RESET_ALL}{Style.DIM} / {Fore.YELLOW}W:{format_bytes(io_write_mb)}{Style.RESET_ALL}{Style.DIM}){Style.RESET_ALL}'
        echo(f"   {'':>24}{Fore.YELLOW}▼ chama{Style.RESET_ALL}{io_label}")
    if libs:
        echo(f'   {Style.DIM}┌─ LIBS {SEP[:BOX_W - 7]}┐{Style.RESET_ALL}')
        for fname, stat in sorted(libs.items(), key=lambda x: x[1]['hits'], reverse=True)[:5]:
            bar = draw_bar(stat['hits'], total_hits, 10, Fore.BLUE)
            short = _lib_short(fname)
            score = bottleneck_score(stat)
            echo(f"   {Style.DIM}│{Style.RESET_ALL}  {Fore.BLUE}{short:<20}{Style.RESET_ALL} {bar} {stat['hits']:>5} hits  {Style.DIM}score:{score:.0f}{Style.RESET_ALL}")
        echo(f'   {Style.DIM}└{SEP}┘{Style.RESET_ALL}')
    proj_hits = flow_data.get('proj_hits', 0)
    lib_hits = flow_data.get('lib_hits', 0)
    if total_hits > 0:
        proj_pct = proj_hits / total_hits * 100
        lib_pct = lib_hits / total_hits * 100
        echo(f'\n   {Style.DIM}Distribuição de hits: {Fore.GREEN}projeto {proj_pct:.0f}%{Style.RESET_ALL}{Style.DIM} │ {Fore.BLUE}libs {lib_pct:.0f}%{Style.RESET_ALL}')

def render_critical_chain(chain: list, context_before: int=3, context_after: int=2):
    """
    Caminho crítico com contexto antes + depois e syntax highlight.

    Cada passo exibe:
      - Cabeçalho com função-pai detectada automaticamente
      - N linhas antes (coloridas por keyword)
      - Hot-line em destaque (branco brilhante, strings em verde)
      - M linhas depois (mostram o que o gargalo retorna/propaga)
    """
    if not chain:
        return
    echo(f'\n   {Fore.RED}🔴 Caminho Crítico (Gargalo Dominante):{Style.RESET_ALL}')
    current_layer = None
    for step in chain:
        fname = step['file']
        lineno = step['line']
        hits = step['hits']
        layer = step['layer']
        if layer != current_layer:
            current_layer = layer
            layer_label = 'PROJ' if layer == 'proj' else 'LIB'
            layer_color = Fore.GREEN if layer == 'proj' else Fore.BLUE
            echo(f"\n   {layer_color}{Style.BRIGHT}[{layer_label}]{Style.RESET_ALL}{Style.DIM} {'─' * 40}{Style.RESET_ALL}")
        _render_predecessor_block(fname, lineno, hits, layer, indent='     ', context_before=context_before, context_after=context_after)
        echo('')

def render_stats_table(stats):
    header = f"{'COMANDO':<15} | {'QTD':<5} | {'T-AVG(ms)':<10} | {'RAM(MB)':<8} | {'I/O R':<8} | {"I/O W":<8}"
    echo(Fore.CYAN + Style.BRIGHT + '\n=== 📈 DASHBOARD DE PERFORMANCE INDUSTRIAL ===')
    echo(header + '\n' + '-' * len(header))
    for cmd, data in sorted(stats.items(), key=lambda x: sum(x[1]['dur']) / len(x[1]['dur']), reverse=True):
        avg = lambda x: sum(x) / len(x) if x else 0
        echo(f"{Fore.WHITE}{cmd:<15}{Style.RESET_ALL} | {len(data['dur']):<5} | {avg(data['dur']):<10.0f} | {avg(data['ram']):<8.1f} | {avg(data['io_r']):<8.2f} | {avg(data['io_w']):<8.2f}")

def render_vulcan_stats(stats, verbose=False):
    if not stats:
        return
    echo(f'   {Fore.MAGENTA}⚡ Vulcan Embedded Telemetry:{Style.RESET_ALL}')
    limit = 5 if verbose else 2
    for fn, data in sorted(stats.items(), key=lambda x: x[1].get('total_ms', 0), reverse=True)[:limit]:
        hits = data.get('hits', 0)
        fb = data.get('fallbacks', 0)
        total_ms = data.get('total_ms', 0.0)
        avg = total_ms / hits if hits > 0 else 0
        fb_str = f'{Fore.RED}{fb} fb{Style.RESET_ALL}' if fb > 0 else f'{Fore.GREEN}0 fb{Style.RESET_ALL}'
        fn_disp = fn[:35] + '..' if len(fn) > 37 else fn
        echo(f'     {Fore.CYAN}⬡{Style.RESET_ALL} {fn_disp:<38} │ {hits:>4} hits | {fb_str} │ Avg: {avg:.3f}ms')
