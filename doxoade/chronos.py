# -*- coding: utf-8 -*-
# doxoade/chronos.py (v94.7 Platinum)
import uuid
import time
import threading
import sys
import pstats
import platform
import os
import json
import io
import cProfile
import collections
import atexit
from datetime import datetime, timezone
from doxoade.tools.doxcolors import Fore
from .database import get_db_connection
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class ResourceMonitor(threading.Thread):
    def __init__(self, pid):
        super().__init__()
        self.pid = pid
        self.running = True
        self.daemon = True
        self.peaks = {
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'io_read_start': 0,
            'io_write_start': 0,
            'io_read_max': 0,
            'io_write_max': 0
        }
    def _scan_tree(self, parent_proc):
        """
        Traversal único da árvore de processos (pai + filhos).

        Cirurgia: substitui três métodos que faziam a mesma coisa
        (_update_tree_metrics, _get_process_tree_stats, _get_tree_io)
        — dois deles eram chamados em sequência no mesmo ciclo de 0.3s,
        resultando em ~1.360 traversals durante uma compilação de 206s
        em vez de ~680. Agora é uma única passagem que coleta tudo.

        Retorna (cpu_total, mem_mb, io_read_bytes, io_write_bytes).
        """
        cpu_total = 0.0
        mem_total = 0.0
        r_total   = 0
        w_total   = 0

        try:
            procs = [parent_proc] + parent_proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            procs = [parent_proc]

        for p in procs:
            try:
                cpu_total += p.cpu_percent(interval=None)
                mem_total += p.memory_info().rss
                io_c       = p.io_counters()
                r_total   += io_c.read_bytes
                w_total   += io_c.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue

        return cpu_total, mem_total / (1024 * 1024), r_total, w_total

    def run(self):
        if not HAS_PSUTIL: return
        
        try:
            parent = psutil.Process(self.pid)
            parent.cpu_percent(interval=None)
            parent = psutil.Process(self.pid)
            # Baseline inicial de I/O
            try:
                io_init = parent.io_counters()
                self.peaks['io_read_start']  = io_init.read_bytes
                self.peaks['io_write_start'] = io_init.write_bytes
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: run\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")

            while self.running:
                # Cirurgia: uma única traversal por ciclo em vez de duas.
                cpu, mem, r_tree, w_tree = self._scan_tree(parent)

                if cpu   > self.peaks['cpu_percent']: self.peaks['cpu_percent'] = cpu
                if mem   > self.peaks['memory_mb']:   self.peaks['memory_mb']   = mem
                if r_tree > self.peaks['io_read_max']:  self.peaks['io_read_max']  = r_tree
                if w_tree > self.peaks['io_write_max']: self.peaks['io_write_max'] = w_tree

                time.sleep(0.3)

            _, _, r_end, w_end = self._scan_tree(parent)
            self.peaks['io_read_end']  = r_end
            self.peaks['io_write_end'] = w_end
        except (psutil.NoSuchProcess, Exception):
            pass

    def stop(self):
        self.running = False

    def get_stats(self):
        """Calcula o delta real de I/O processado."""
        read_bytes  = max(0, self.peaks['io_read_max']  - self.peaks['io_read_start'])
        write_bytes = max(0, self.peaks['io_write_max'] - self.peaks['io_write_start'])
        
        return {
            'cpu':   round(self.peaks['cpu_percent'], 1),
            'ram':   round(self.peaks['memory_mb'], 1),
            'read':  round(read_bytes  / (1024 * 1024), 3),
            'write': round(write_bytes / (1024 * 1024), 3),
        }

    def _check_memory_safety(self, mem_mb):
        """Aegis Guard: Impede que o Doxoade devore a RAM do usuário (Leak protection)."""
        RAM_SAFETY_THRESHOLD = 1024.0
        
        if mem_mb > RAM_SAFETY_THRESHOLD:
            print(f"\n🚨 {Fore.RED}[AEGIS MEMORY GUARD]{Fore.RESET} Doxoade excedeu limite de segurança (1GB).")
            print("   > Abortando tarefa para evitar instabilidade no Windows.")
            os._exit(1)


class CodeSampler(threading.Thread):
    # Cirurgia: filtro movido para constante de classe (frozenset).
    _NOISE_SUFFIXES = frozenset({"<frozen", "chronos.py", "threading.py"})

    def __init__(self, interval=0.01):
        super().__init__(daemon=True)
        self.interval = interval
        self.running = True
        self.samples = collections.defaultdict(int)
        self.main_thread_id = threading.main_thread().ident

    def run(self):
        lib_path    = os.path.dirname(os.__file__).lower().replace('\\', '/')
        noise_check = self._NOISE_SUFFIXES

        while self.running:
            time.sleep(self.interval)
            try:
                frame = sys._current_frames().get(self.main_thread_id)
                while frame:
                    filename  = frame.f_code.co_filename
                    norm_file = filename.lower().replace('\\', '/')

                    if (any(x in norm_file for x in noise_check)
                            or norm_file.startswith(lib_path)):
                        frame = frame.f_back
                        continue

                    self.samples[(os.path.abspath(filename), frame.f_lineno)] += 1
                    break
            except Exception as e:
                import sys as dox_exc_sys
                _, exc_obj, exc_tb = dox_exc_sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_number = exc_tb.tb_lineno
                print(f"\033[0m \033[1m Filename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \033[0m")

    def stop(self): self.running = False

    def get_hot_lines(self, limit=10):
        return sorted(self.samples.items(), key=lambda item: item[1], reverse=True)[:limit]


class ChronosRecorder:
    def __init__(self):
        self.session_uuid   = str(uuid.uuid4())
        self.monitor        = None
        self.profiler       = None
        self.sampler        = None
        self.system_context = {}
        self._ended         = False          # guarda contra double-record
        self._perf_start    = None           # perf_counter no inicio — usado pelo atexit

    def start_command(self, ctx):
        if ctx.invoked_subcommand:
            self.cmd_name = ctx.invoked_subcommand
        else:
            self.cmd_name = ctx.command.name if ctx else "unknown"

        self.system_context = {
            "os":        platform.system(),
            "release":   platform.release(),
            "arch":      platform.machine(),
            "python":    platform.python_version(),
            "processor": platform.processor(),
            "cores":     psutil.cpu_count() if HAS_PSUTIL else 1,
        }

        self.monitor = ResourceMonitor(os.getpid())
        self.monitor.start()

        self.profiler = cProfile.Profile()
        self.profiler.enable()

        self.sampler = CodeSampler(interval=0.01)
        self.sampler.start()

        self.start_timestamp = datetime.now(timezone.utc).isoformat()
        self.full_cmd        = " ".join(sys.argv)
        self.work_dir        = os.getcwd()
        self._perf_start     = time.perf_counter()
        self._ended          = False

        # ── Garantia atexit ────────────────────────────────────────────────────
        # Click standalone_mode chama sys.exit() ANTES que result_callback
        # consiga persistir. O atexit é a rede de segurança que garante que
        # QUALQUER comando seja gravado, independente de como o processo encerra.
        # Se end_command já foi chamado antes (via result_callback), _ended=True
        # e o atexit se torna no-op — sem double-record.
        atexit.register(self._atexit_flush)

    def _atexit_flush(self):
        """
        Rede de segurança: chamada pelo atexit se end_command não foi invocado.
        Calcula duration_ms a partir de _perf_start para precisão real.
        exit_code = 0 (SystemExit(0)) na maioria dos casos de saída limpa do Click.
        """
        if self._ended or self._perf_start is None:
            return
        duration_ms = (time.perf_counter() - self._perf_start) * 1000
        self.end_command(exit_code=0, duration_ms=duration_ms)

    def end_command(self, exit_code, duration_ms):
        # Guarda idempotência: se já foi chamado (via result_callback ou atexit),
        # retorna imediatamente para evitar gravar o mesmo comando duas vezes.
        if self._ended:
            return
        self._ended = True

        if not self.monitor:
            return

        self.monitor.stop()
        self.sampler.stop()

        resources = self.monitor.get_stats()
        hot_lines = self.sampler.get_hot_lines()

        self.profiler.disable()
        s  = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(15)
        profile_text = s.getvalue()

        top_funcs = []
        for line in profile_text.splitlines():
            if "(" in line and ")" in line and os.getcwd() in line:
                top_funcs.append(line.strip())

        line_profile_data = []
        for (fname, lineno), hits in hot_lines:
            line_profile_data.append({"file": fname.replace('\\', '/'), "line": lineno, "hits": hits})

        # Captura os stats do Vulcan para o system_info
        if hasattr(self, 'vulcan_stats'):
            self.system_context['vulcan_stats'] = self.vulcan_stats

        try:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO command_history 
                (session_uuid, timestamp, command_name, full_command_line, working_dir,
                 exit_code, duration_ms, cpu_percent, peak_memory_mb,
                 io_read_mb, io_write_mb, line_profile_data, system_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_uuid,
                datetime.now(timezone.utc).isoformat(),
                self.cmd_name,
                " ".join(sys.argv),
                os.getcwd(),
                exit_code,
                duration_ms,
                resources['cpu'],
                resources['ram'],
                resources['read'],
                resources['write'],
                json.dumps(line_profile_data),
                json.dumps(self.system_context),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            import sys as dox_exc_sys
            _, exc_obj, exc_tb = dox_exc_sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f"\033[0m \033[1m Filename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {e} ■ Exception value: {exc_obj} \033[0m")

    def check_vulcan_efficiency(self, func_name, py_time, native_time):
        gain = py_time / native_time
        if gain < 1.1:
            pass


chronos_recorder = ChronosRecorder()