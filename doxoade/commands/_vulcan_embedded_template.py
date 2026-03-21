# -*- coding: utf-8 -*-
# doxoade/commands/_vulcan_embedded_template.py
"""
Template do vulcan_embedded.py gerado pelo Vulcan bootstrap.

Isolado em arquivo proprio para que o CodeSampler nao registre
linhas do literal de string como hot lines em vulcan_cmd_bootstrap.py.
"""

VULCAN_EMBEDDED_CONTENT = r'''# -*- coding: utf-8 -*-
"""
vulcan_embedded.py — Chronos Lite v4.
Gerado automaticamente pelo doxoade. Nao edite manualmente.

Novidades v4:
  _LibCodeSampler       — amostrador dedicado para frames de site-packages
                          (libs de terceiros). Hot lines gravadas em
                          sys_info["lib_hot_lines"] — exibidas pelo doxoade
                          telemetry -v como secao separada das hot lines do projeto.
  _ExternalCodeSampler  — inalterado: frames do projeto alvo → line_profile_data.
  _collect_click_context — inalterado: para em tokens nao-identificador.
"""

from functools import wraps
from pathlib import Path
import sys
import os
import re
import importlib.util
import importlib.machinery
import time
import atexit
import json
import sqlite3
import uuid
import datetime
import threading
import collections

# ── Boot timestamp ─────────────────────────────────────────────────────────────
_cl_boot_time = time.monotonic()

# ── Dicionario de picos ────────────────────────────────────────────────────────
_cl_peaks = {
    'cpu':          0.0,
    'ram_mb':       0.0,
    'io_r_bytes':   0,
    'io_w_bytes':   0,
    'io_r_count':   0,
    'io_w_count':   0,
    '_io_r_base':   0,
    '_io_w_base':   0,
    '_io_rc_base':  0,
    '_io_wc_base':  0,
}

_cl_psutil = None
try:
    import psutil as _cl_psutil
except ImportError:
    pass


# ── Monitor de Recursos ────────────────────────────────────────────────────────

class _ChronosLiteMonitor(threading.Thread):
    """Thread daemon: CPU, RAM, I/O bytes e syscall count a cada 0.3s."""

    def __init__(self):
        super().__init__(daemon=True)
        self._running = True

    def run(self):
        if not _cl_psutil:
            return
        try:
            proc = _cl_psutil.Process(os.getpid())
            proc.cpu_percent(interval=None)

            try:
                io0 = proc.io_counters()
                _cl_peaks['_io_r_base']  = io0.read_bytes
                _cl_peaks['_io_w_base']  = io0.write_bytes
                _cl_peaks['_io_rc_base'] = io0.read_count
                _cl_peaks['_io_wc_base'] = io0.write_count
            except (AttributeError, _cl_psutil.AccessDenied):
                pass

            while self._running:
                try:
                    cpu = proc.cpu_percent(interval=None)
                    ram = proc.memory_info().rss / (1024 * 1024)

                    if cpu > _cl_peaks['cpu']:    _cl_peaks['cpu']    = cpu
                    if ram > _cl_peaks['ram_mb']: _cl_peaks['ram_mb'] = ram

                    try:
                        io = proc.io_counters()
                        if io.read_bytes  > _cl_peaks['io_r_bytes']: _cl_peaks['io_r_bytes'] = io.read_bytes
                        if io.write_bytes > _cl_peaks['io_w_bytes']: _cl_peaks['io_w_bytes'] = io.write_bytes
                        if io.read_count  > _cl_peaks['io_r_count']: _cl_peaks['io_r_count'] = io.read_count
                        if io.write_count > _cl_peaks['io_w_count']: _cl_peaks['io_w_count'] = io.write_count
                    except (AttributeError, _cl_psutil.AccessDenied):
                        pass

                except (_cl_psutil.NoSuchProcess, _cl_psutil.AccessDenied):
                    break
                except Exception:
                    pass

                time.sleep(0.3)

        except Exception:
            pass

    def stop(self):
        self._running = False


# ── Helpers de filtro de frame ─────────────────────────────────────────────────
# Calculados uma unica vez no import; reutilizados pelos dois samplers.

def _get_stdlib_prefix():
    try:
        import sysconfig as _sc
        return os.path.normcase(os.path.abspath(_sc.get_path('stdlib') or ''))
    except Exception:
        return ''

_STDLIB_PREFIX = _get_stdlib_prefix()

# Sufixos de infraestrutura ignorados por ambos os samplers
_NOISE_SUFFIXES = frozenset({
    "<frozen",
    "threading.py",
    "chronos.py",
    "_vulcan_embedded",
    "vulcan_embedded",
    "linecache.py",
    "importlib",
})

def _is_noise(norm_file):
    """Retorna True se o frame e de infraestrutura (nao e nem projeto nem lib)."""
    return any(n in norm_file for n in _NOISE_SUFFIXES)

def _is_stdlib(norm_file):
    return bool(_STDLIB_PREFIX) and os.path.normcase(
        os.path.abspath(norm_file)
    ).startswith(_STDLIB_PREFIX)

def _is_site_packages(norm_file):
    return 'site-packages' in norm_file or 'dist-packages' in norm_file


# ── Amostrador do Projeto ──────────────────────────────────────────────────────

class _ExternalCodeSampler(threading.Thread):
    """
    Amostrador de frames do PROJETO ALVO (exclui stdlib e site-packages).
    Resultado → line_profile_data no DB (renderizado por 'doxoade telemetry -v').
    """

    def __init__(self, interval: float = 0.01):
        super().__init__(daemon=True)
        self.interval  = interval
        self._running  = True
        self._samples  = collections.defaultdict(int)
        self._main_tid = threading.main_thread().ident

    def run(self):
        samples = self._samples
        while self._running:
            time.sleep(self.interval)
            try:
                frame = sys._current_frames().get(self._main_tid)
                while frame:
                    fname     = frame.f_code.co_filename
                    norm_file = fname.lower().replace('\\', '/')

                    if _is_noise(norm_file):
                        frame = frame.f_back; continue
                    if _is_stdlib(norm_file):
                        frame = frame.f_back; continue
                    if _is_site_packages(norm_file):
                        frame = frame.f_back; continue

                    # Frame do projeto alvo
                    samples[(os.path.abspath(fname), frame.f_lineno)] += 1
                    break
            except Exception:
                pass

    def stop(self):
        self._running = False

    def get_hot_lines(self, limit: int = 5):
        top = sorted(self._samples.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {"file": fname.replace('\\', '/'), "line": lineno, "hits": hits}
            for (fname, lineno), hits in top
        ]


# ── Amostrador de Libs ─────────────────────────────────────────────────────────

class _LibCodeSampler(threading.Thread):
    """
    Amostrador de frames de LIBS DE TERCEIROS (site-packages / dist-packages).

    Logica inversa do _ExternalCodeSampler:
      aceita frames de site-packages, rejeita tudo o mais.

    Isso responde a pergunta: "qual funcao de qual lib esta bloqueando o
    processo?" — ex.: `llama_cpp/_internals.py:NNN eval() 2547 hits` indica
    que o gargalo e o proprio kernel de inferencia da llama-cpp.

    Resultado → sys_info["lib_hot_lines"] no DB.
    Renderizado por 'doxoade telemetry -v' como secao separada.
    """

    def __init__(self, interval: float = 0.01):
        super().__init__(daemon=True)
        self.interval  = interval
        self._running  = True
        self._samples  = collections.defaultdict(int)
        self._main_tid = threading.main_thread().ident

    def run(self):
        samples = self._samples
        while self._running:
            time.sleep(self.interval)
            try:
                frame = sys._current_frames().get(self._main_tid)
                while frame:
                    fname     = frame.f_code.co_filename
                    norm_file = fname.lower().replace('\\', '/')

                    if _is_noise(norm_file):
                        frame = frame.f_back; continue
                    if _is_stdlib(norm_file):
                        frame = frame.f_back; continue

                    if not _is_site_packages(norm_file):
                        # Nao e lib de terceiro — sobe ate achar um
                        frame = frame.f_back; continue

                    # Frame de lib de terceiro
                    samples[(os.path.abspath(fname), frame.f_lineno)] += 1
                    break
            except Exception:
                pass

    def stop(self):
        self._running = False

    def get_hot_lines(self, limit: int = 5):
        top = sorted(self._samples.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {"file": fname.replace('\\', '/'), "line": lineno, "hits": hits}
            for (fname, lineno), hits in top
        ]


# Inicia os tres coletores imediatamente — captam todo o ciclo de vida
_cl_monitor = _ChronosLiteMonitor()
_cl_monitor.start()

_cl_sampler     = _ExternalCodeSampler(interval=0.01)
_cl_lib_sampler = _LibCodeSampler(interval=0.01)
_cl_sampler.start()
_cl_lib_sampler.start()

_vulcan_stats = {}


# ── Coletor 1: Contexto Click ──────────────────────────────────────────────────

_CMD_TOKEN_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')

def _collect_click_context():
    """
    Extrai cadeia de subcomandos Click e arquivo executado de sys.argv.
    Para no primeiro token que nao bate com _CMD_TOKEN_RE (argumento posicional).
    """
    if not sys.argv:
        return 'unknown', 'unknown'

    script_file = sys.argv[0]
    cmd_parts   = []
    for token in sys.argv[1:]:
        if token.startswith('-'):
            break
        if not _CMD_TOKEN_RE.match(token):
            break
        cmd_parts.append(token)

    cmd_chain = ' '.join(cmd_parts) if cmd_parts else Path(script_file).stem
    return cmd_chain, script_file


# ── Coletor 2: Uso de Libs ─────────────────────────────────────────────────────

def _collect_lib_usage():
    libs = {}
    for name, mod in list(sys.modules.items()):
        if '.' in name or name.startswith('_'):
            continue
        try:
            mfile = getattr(mod, '__file__', None)
            if not mfile:
                continue
            norm = os.path.normcase(os.path.abspath(mfile))
            if 'site-packages' not in norm and 'dist-packages' not in norm:
                continue
            if _STDLIB_PREFIX and norm.startswith(_STDLIB_PREFIX):
                continue
            version = (
                getattr(mod, '__version__', None)
                or getattr(mod, 'VERSION',    None)
                or getattr(mod, 'version',    None)
            )
            libs[name] = str(version) if version is not None else None
        except Exception:
            continue
    return libs


# ── Coletor 3: Snapshot de Disco ──────────────────────────────────────────────

def _collect_disk_snapshot():
    result = {}
    try:
        cwd = os.getcwd()
        if _cl_psutil:
            du = _cl_psutil.disk_usage(cwd)
            result['disk_total_gb'] = round(du.total   / (1024 ** 3), 2)
            result['disk_used_gb']  = round(du.used    / (1024 ** 3), 2)
            result['disk_free_gb']  = round(du.free    / (1024 ** 3), 2)
            result['disk_used_pct'] = round(du.percent, 1)
        else:
            import shutil
            total, used, free = shutil.disk_usage(cwd)
            result['disk_total_gb'] = round(total / (1024 ** 3), 2)
            result['disk_used_gb']  = round(used  / (1024 ** 3), 2)
            result['disk_free_gb']  = round(free  / (1024 ** 3), 2)
            result['disk_used_pct'] = round(used / total * 100, 1) if total else 0.0
    except Exception:
        pass
    result['io_read_count']  = max(0, _cl_peaks['io_r_count'] - _cl_peaks['_io_rc_base'])
    result['io_write_count'] = max(0, _cl_peaks['io_w_count'] - _cl_peaks['_io_wc_base'])
    return result


# ── Dump principal (atexit) ────────────────────────────────────────────────────

def _dump_vulcan_telemetry():
    """
    Agrega e sincroniza telemetria completa ao fechar o processo.

    Colunas diretas do DB:
      command_name      — cadeia de subcomandos Click
      full_command_line — sys.argv completo  ← exibido por 'doxoade telemetry -v'
      duration_ms / cpu_percent / peak_memory_mb / io_read_mb / io_write_mb
      line_profile_data — hot lines do PROJETO (renderizadas automaticamente)

    system_info JSON:
      script_file    — arquivo fisico executado
      source_project — diretorio de trabalho
      libs           — libs de terceiros + versoes
      disk           — uso da particao + io_read/write_count
      lib_hot_lines  — hot lines de LIBS DE TERCEIROS ← nova secao no telemetry -v
      vulcan_stats   — timing de funcoes otimizadas (inalterado)
    """
    _cl_monitor.stop()
    _cl_sampler.stop()
    _cl_lib_sampler.stop()

    duration_ms = (time.monotonic() - _cl_boot_time) * 1000
    cpu  = round(_cl_peaks['cpu'],    1)
    ram  = round(_cl_peaks['ram_mb'], 1)
    io_r = round(max(0, _cl_peaks['io_r_bytes'] - _cl_peaks['_io_r_base']) / (1024 * 1024), 3)
    io_w = round(max(0, _cl_peaks['io_w_bytes'] - _cl_peaks['_io_w_base']) / (1024 * 1024), 3)

    if not _vulcan_stats and cpu == 0.0 and ram == 0.0:
        return

    cmd_chain, script_file = _collect_click_context()
    libs                   = _collect_lib_usage()
    disk                   = _collect_disk_snapshot()
    hot_lines              = _cl_sampler.get_hot_lines(limit=5)
    lib_hot_lines          = _cl_lib_sampler.get_hot_lines(limit=5)

    sys_info = {
        "note":           "Vulcan Standalone Telemetry",
        "script_file":    script_file,
        "source_project": os.getcwd(),
        "libs":           libs,
        "disk":           disk,
        "lib_hot_lines":  lib_hot_lines,   # hot lines de libs de terceiros
        "vulcan_stats":   _vulcan_stats,
    }

    # ── Destino 1: ORN jsonl ───────────────────────────────────────────────────
    if os.environ.get("VULCAN_TELEMETRY_SYNC", "1") != "0":
        try:
            out_dir = Path("telemetry")
            if out_dir.exists() or "ORN" in str(Path.cwd().name).upper():
                out_dir.mkdir(exist_ok=True)
                payload = {
                    "captured_at_unix": int(time.time()),
                    "cmd_chain":        cmd_chain,
                    "script_file":      script_file,
                    "full_command":     " ".join(sys.argv),
                    "duration_ms":      round(duration_ms, 1),
                    "cpu_percent":      cpu,
                    "ram_mb":           ram,
                    "io_read_mb":       io_r,
                    "io_write_mb":      io_w,
                    "hot_lines":        hot_lines,
                    "lib_hot_lines":    lib_hot_lines,
                    "libs":             libs,
                    "disk":             disk,
                    "vulcan_stats":     _vulcan_stats,
                }
                with (out_dir / "vulcan_runtime.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── Destino 2: Doxoade Global DB ──────────────────────────────────────────
    if "doxoade.chronos" not in sys.modules and os.environ.get("VULCAN_TELEMETRY_SYNC", "1") != "0":
        try:
            db_path = Path.home() / '.doxoade' / 'doxoade.db'
            if db_path.exists():
                if cmd_chain and cmd_chain != 'unknown':
                    db_cmd = "vulcan_ext_" + cmd_chain.replace(' ', '_')
                else:
                    db_cmd = "vulcan_ext_" + Path(script_file).stem

                with sqlite3.connect(str(db_path), timeout=2.0) as conn:
                    conn.execute("""
                        INSERT INTO command_history
                        (session_uuid, timestamp, command_name, full_command_line, working_dir,
                         exit_code, duration_ms, cpu_percent, peak_memory_mb,
                         io_read_mb, io_write_mb, line_profile_data, system_info)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        db_cmd,
                        " ".join(sys.argv),           # full_command_line: argv completo
                        os.getcwd(),
                        0,
                        round(duration_ms, 1),
                        cpu,
                        ram,
                        io_r,
                        io_w,
                        json.dumps(hot_lines,     ensure_ascii=False),  # line_profile_data
                        json.dumps(sys_info,      ensure_ascii=False),
                    ))
        except Exception:
            pass

    # ── Destino 3: Console opt-in ─────────────────────────────────────────────
    if os.environ.get("VULCAN_TELEMETRY") == "1":
        try:
            import linecache
            sep = "=" * 68
            print("\n" + sep)
            print("  VULCAN EMBEDDED TELEMETRY  (Chronos Lite v4)")
            print(sep)
            print(f"  Comando     : {cmd_chain}")
            print(f"  Full cmd    : {' '.join(sys.argv)}")
            print(f"  Arquivo     : {script_file}")
            print(f"  Duracao     : {duration_ms:>9.0f} ms")
            print(f"  CPU Peak    : {cpu:>9.1f} %")
            print(f"  RAM Peak    : {ram:>9.1f} MB")
            print(f"  I/O Leitura : {io_r:>9.3f} MB  ({disk.get('io_read_count',  0):>6} ops)")
            print(f"  I/O Escrita : {io_w:>9.3f} MB  ({disk.get('io_write_count', 0):>6} ops)")
            if disk.get('disk_total_gb'):
                print(
                    f"  Disco       : "
                    f"{disk['disk_used_gb']:.1f}/{disk['disk_total_gb']:.1f} GB  "
                    f"({disk['disk_used_pct']}% | "
                    f"{disk['disk_free_gb']:.1f} GB livres)"
                )
            if hot_lines:
                print(f"\n  Hot Lines — Projeto:")
                for item in hot_lines:
                    content = linecache.getline(item['file'], item['line']).strip()
                    short   = item['file'].replace('\\', '/').split('/')[-1]
                    print(f"    {short}:{item['line']:<4} ({item['hits']:>4} hits) > {content}")
            if lib_hot_lines:
                print(f"\n  Hot Lines — Libs:")
                for item in lib_hot_lines:
                    content = linecache.getline(item['file'], item['line']).strip()
                    # Extrai nome da lib do caminho (1 nivel apos site-packages)
                    parts = item['file'].replace('\\', '/').split('site-packages/')
                    short = parts[1].split('/')[0] + '/' + item['file'].replace('\\', '/').split('/')[-1] if len(parts) > 1 else item['file'].replace('\\', '/').split('/')[-1]
                    print(f"    {short}:{item['line']:<4} ({item['hits']:>4} hits) > {content}")
            if libs:
                lib_str = '  '.join(
                    f"{k}({v})" if v else k for k, v in list(libs.items())[:10]
                )
                print(f"\n  Libs ({len(libs):>2}) : {lib_str}")
            if _vulcan_stats:
                print(f"\n  {'Funcao':<32} {'Hits':>6}  {'Total(ms)':>10}  {'Avg(ms)':>8}  {'Fallbk':>6}")
                print("  " + "-" * 64)
                for fn, data in sorted(
                    _vulcan_stats.items(),
                    key=lambda x: x[1]['total_ms'],
                    reverse=True,
                ):
                    avg      = data['total_ms'] / data['hits'] if data['hits'] > 0 else 0
                    name_str = (fn[:29] + "...") if len(fn) > 32 else fn
                    print(
                        f"  {name_str:<32} {data['hits']:>6}  "
                        f"{data['total_ms']:>10.3f}  {avg:>8.3f}  {data['fallbacks']:>6}"
                    )
            print(sep + "\n")
        except Exception:
            pass


atexit.register(_dump_vulcan_telemetry)

# Resto do codigo vulcan_embedded permanece intacto...
'''