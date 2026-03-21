# -*- coding: utf-8 -*-
"""
Telemetry Utils v3.8 - Córtex Analítico de Recursos.
Focado em precisão de I/O, análise de vazão e fluxo entre arquivos.
"""
import json
# [DOX-UNUSED] import os


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

# Marcadores que indicam que um arquivo pertence a uma lib de terceiros,
# mesmo quando ele vem misturado em line_profile_data junto com o projeto.
_LIB_MARKERS = (
    'site-packages/',
    'site-packages\\',
    'dist-packages/',
    'dist-packages\\',
    'venv/Lib/',
    'venv\\Lib\\',
    'venv/lib/',
    'venv\\lib\\',
)


# ─── JSON ────────────────────────────────────────────────────────────────────

def parse_json_safe(data):
    if not data: return {}
    try: return json.loads(data)
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info()  # exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: parse_json_safe\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return {}


# ─── FORMATAÇÃO ──────────────────────────────────────────────────────────────

def format_bytes(size_mb):
    """Converte MB para a unidade mais legível (PASC-6.4)."""
    bytes_val = size_mb * 1024 * 1024
    if bytes_val < 1024:          return f"{bytes_val:.0f} B"
    if bytes_val < 1024 * 1024:   return f"{bytes_val/1024:.1f} KB"
    return f"{size_mb:.1f} MB"


# ─── STATUS DE RECURSOS ───────────────────────────────────────────────────────

def get_resource_status(cpu, ram, io_total):
    status = {"cpu": "Ocioso", "ram": "Leve", "io": "Baixo"}
    if cpu > 80:        status["cpu"] = "Crítico"
    elif cpu > 50:      status["cpu"] = "Alto"
    if ram > 400:       status["ram"] = "Pesado"
    elif ram > 150:     status["ram"] = "Moderado"
    if io_total > 50:   status["io"]  = "Intenso"
    elif io_total > 1:  status["io"]  = "Ativo"
    elif io_total > 0.01: status["io"] = "Mínimo"
    return status


# ─── AGREGAÇÃO DE STATS ───────────────────────────────────────────────────────

def aggregate_command_stats(rows):
    stats = {}
    for row in rows:
        cmd = row['command_name'] or "unknown"
        if cmd not in stats:
            stats[cmd] = {'dur': [], 'cpu': [], 'ram': [], 'io_r': [], 'io_w': []}
        if row['duration_ms']:    stats[cmd]['dur'].append(row['duration_ms'])
        if row['cpu_percent']:    stats[cmd]['cpu'].append(row['cpu_percent'])
        if row['peak_memory_mb']: stats[cmd]['ram'].append(row['peak_memory_mb'])
        stats[cmd]['io_r'].append(row['io_read_mb']  or 0)
        stats[cmd]['io_w'].append(row['io_write_mb'] or 0)
    return stats


# ─── HELPERS DE CLASSIFICAÇÃO ─────────────────────────────────────────────────

def _is_lib_path(fname: str) -> bool:
    """
    Retorna True se o caminho pertence a uma lib de terceiros.
    Detecta site-packages, dist-packages e venv/Lib mesmo quando o profiler
    mistura tudo em line_profile_data junto com código do projeto.
    """
    norm = fname.replace('\\', '/')
    return any(m.replace('\\', '/') in norm for m in _LIB_MARKERS)


# ─── FLUXO DE DADOS ENTRE ARQUIVOS ───────────────────────────────────────────

def aggregate_file_stats(hot_data: list) -> dict:
    """
    Agrupa hot-lines por arquivo.

    Entrada:  lista de dicts {file, line, hits}
    Saída:    {filename: {'hits': int, 'hot_lines': [(lineno, hits), ...]}}
    """
    stats: dict = {}
    for item in hot_data:
        fname = item['file']
        hits  = item['hits']
        if fname not in stats:
            stats[fname] = {'hits': 0, 'hot_lines': []}
        stats[fname]['hits'] += hits
        stats[fname]['hot_lines'].append((item['line'], hits))

    for fname in stats:
        stats[fname]['hot_lines'].sort(key=lambda x: x[1], reverse=True)
    return stats


def build_flow_data(proj_data: list, lib_data: list) -> dict:
    """
    Constrói estrutura unificada de fluxo entre camadas.

    Separa AUTOMATICAMENTE entradas de proj_data que pertençam a libs
    (site-packages / venv/Lib) das que são código real do projeto.

    Isso corrige o bug onde colorama/win32.py, click/_winconsole.py e outros
    apareciam na caixa PROJETO porque o profiler despeja tudo junto em
    line_profile_data, sem distinção de origem.

    Retorna:
        {
            'proj':       {filename: {hits, hot_lines}},
            'libs':       {filename: {hits, hot_lines}},
            'total_hits': int,
            'proj_hits':  int,
            'lib_hits':   int,
        }
    """
    real_proj: list = []
    auto_libs: list = []

    for item in (proj_data or []):
        if _is_lib_path(item['file']):
            auto_libs.append(item)
        else:
            real_proj.append(item)

    # lib_data (system_info['lib_hot_lines']) já é explicitamente de libs
    all_libs = auto_libs + (lib_data or [])

    proj_stats = aggregate_file_stats(real_proj)
    lib_stats  = aggregate_file_stats(all_libs)

    proj_hits  = sum(v['hits'] for v in proj_stats.values())
    lib_hits   = sum(v['hits'] for v in lib_stats.values())

    return {
        'proj':       proj_stats,
        'libs':       lib_stats,
        'total_hits': proj_hits + lib_hits,
        'proj_hits':  proj_hits,
        'lib_hits':   lib_hits,
    }


def bottleneck_score(file_stat: dict, io_mb: float = 0.0) -> float:
    """Score composto: hits + (io_mb × 2)."""
    return file_stat['hits'] * 1.0 + io_mb * 2.0


def find_critical_chain(flow_data: dict, max_steps: int = 4) -> list:
    """
    Extrai o caminho crítico: top-N linhas mais quentes,
    ordenadas projeto → libs.

    Retorna lista de dicts:
        [{'file', 'line', 'hits', 'layer'}, ...]   layer = 'proj' | 'lib'
    """
    chain = []

    proj_limit = (max_steps + 1) // 2
    for fname, stat in sorted(
        flow_data.get('proj', {}).items(),
        key=lambda x: x[1]['hits'], reverse=True
    )[:proj_limit]:
        for lineno, hits in stat['hot_lines'][:1]:
            chain.append({'file': fname, 'line': lineno, 'hits': hits, 'layer': 'proj'})

    lib_limit = max(1, max_steps - len(chain))
    for fname, stat in sorted(
        flow_data.get('libs', {}).items(),
        key=lambda x: x[1]['hits'], reverse=True
    )[:lib_limit]:
        for lineno, hits in stat['hot_lines'][:1]:
            chain.append({'file': fname, 'line': lineno, 'hits': hits, 'layer': 'lib'})

    return chain