# doxoade/chronos.py
import os
import sys
import time
import uuid
import json
import threading
import cProfile
import pstats
import io
import platform
import collections
from datetime import datetime, timezone
# [DOX-UNUSED] from pathlib import Path
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
            'io_read_end': 0,
            'io_write_end': 0
        }

    def _get_process_tree_stats(self, parent_proc):
        """[NOVO] Soma recursos da árvore de processos (Pai + Filhos)."""
        cpu_total = 0.0
        mem_total = 0.0
        
        # Inclui o pai
        try:
            cpu_total += parent_proc.cpu_percent(interval=None) 
            mem_total += parent_proc.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError): pass

        # Inclui os filhos (recursivo)
        try:
            children = parent_proc.children(recursive=True)
            for child in children:
                try:
                    cpu_total += child.cpu_percent(interval=None)
                    mem_total += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        
        return cpu_total, mem_total / (1024 * 1024)

    def _get_tree_io(self, parent_proc):
        """[NOVO] Soma I/O da árvore."""
        r = 0
        w = 0
        procs = [parent_proc]
        try: procs.extend(parent_proc.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass

        for p in procs:
            try:
                io = p.io_counters()
                r += io.read_bytes
                w += io.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError): pass
        return r, w

    def run(self):
        if not HAS_PSUTIL: return
        
        try:
            parent = psutil.Process(self.pid)
            parent.cpu_percent(interval=None)
            
            r_start, w_start = self._get_tree_io(parent)
            self.peaks['io_read_start'] = r_start
            self.peaks['io_write_start'] = w_start

            while self.running:
                time.sleep(0.5) 
                
                cpu, mem = self._get_process_tree_stats(parent)
                
                if cpu > self.peaks['cpu_percent']: self.peaks['cpu_percent'] = cpu
                if mem > self.peaks['memory_mb']: self.peaks['memory_mb'] = mem
                
            r_end, w_end = self._get_tree_io(parent)
            self.peaks['io_read_end'] = r_end
            self.peaks['io_write_end'] = w_end

        except (psutil.NoSuchProcess, Exception):
            pass

    def stop(self):
        self.running = False

    def get_stats(self):
        # [FIX] Garante cálculo de IO mesmo se processo morreu rápido
        read_bytes = max(0, self.peaks['io_read_end'] - self.peaks['io_read_start'])
        write_bytes = max(0, self.peaks['io_write_end'] - self.peaks['io_write_start'])
        
        return {
            'cpu': round(self.peaks['cpu_percent'], 1),
            'ram': round(self.peaks['memory_mb'], 1),
            'read': round(read_bytes / (1024*1024), 2),
            'write': round(write_bytes / (1024*1024), 2)
        }

# --- CodeSampler Mantido Igual ---
class CodeSampler(threading.Thread):
    def __init__(self, interval=0.01):
        super().__init__()
        self.interval = interval
        self.running = True
        self.daemon = True
        self.samples = collections.defaultdict(int)
        self.main_thread_id = threading.main_thread().ident

    def run(self):
        while self.running:
            time.sleep(self.interval)
            try:
                frame = sys._current_frames().get(self.main_thread_id)
                if frame:
                    filename = frame.f_code.co_filename
                    if "doxoade" in filename or os.getcwd() in filename:
                        self.samples[(filename, frame.f_lineno)] += 1
            except Exception: pass

    def stop(self): self.running = False
    def get_hot_lines(self, limit=5):
        return sorted(self.samples.items(), key=lambda item: item[1], reverse=True)[:limit]

class ChronosRecorder:
    def __init__(self):
        self.session_uuid = str(uuid.uuid4())
        self.monitor = None
        self.profiler = None
        self.sampler = None
        self.system_context = {}
        
    def start_command(self, ctx):
        if ctx.invoked_subcommand:
            self.cmd_name = ctx.invoked_subcommand
        else:
            self.cmd_name = ctx.command.name if ctx else "unknown"

        self.system_context = {
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "processor": platform.processor(),
            "cores": psutil.cpu_count() if HAS_PSUTIL else 1
        }

        self.monitor = ResourceMonitor(os.getpid())
        self.monitor.start()
        
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        self.sampler = CodeSampler(interval=0.01)
        self.sampler.start()
        
        self.start_timestamp = datetime.now(timezone.utc).isoformat()
        self.full_cmd = " ".join(sys.argv)
        self.work_dir = os.getcwd()

    def end_command(self, exit_code, duration_ms):
        if not self.monitor: return

        self.monitor.stop()
        self.sampler.stop()
        
        resources = self.monitor.get_stats()
        hot_lines = self.sampler.get_hot_lines()
        
        self.profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(15)
        profile_text = s.getvalue()
        
        top_funcs = []
        for line in profile_text.splitlines():
            if "(" in line and ")" in line and os.getcwd() in line:
                top_funcs.append(line.strip())

        line_profile_data = []
        for (fname, lineno), hits in hot_lines:
            clean_name = fname.replace(os.getcwd(), "").strip(os.sep)
            line_profile_data.append({"file": clean_name, "line": lineno, "hits": hits})

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO command_history 
                (session_uuid, timestamp, command_name, full_command_line, working_dir, exit_code, duration_ms, 
                 cpu_percent, peak_memory_mb, io_read_mb, io_write_mb, profile_data, system_info, line_profile_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_uuid,
                self.start_timestamp,
                self.cmd_name,
                self.full_cmd,
                self.work_dir,
                exit_code,
                duration_ms,
                resources['cpu'],
                resources['ram'],
                resources['read'],
                resources['write'],
                json.dumps(top_funcs[:10]),
                json.dumps(self.system_context),
                json.dumps(line_profile_data)
            ))
            conn.commit()
            conn.close()
        except Exception: pass

chronos_recorder = ChronosRecorder()