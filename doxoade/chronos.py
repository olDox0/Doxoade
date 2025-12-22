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
from pathlib import Path
from .database import get_db_connection

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class ResourceMonitor(threading.Thread):
    # ... (MANTENHA A CLASSE ResourceMonitor IGUAL A ANTES) ...
    def __init__(self, pid):
        super().__init__()
        self.pid = pid
        self.running = True
        self.daemon = True # Importante
        self.peaks = {
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'io_read_start': 0,
            'io_write_start': 0,
            'io_read_end': 0,
            'io_write_end': 0
        }

    def run(self):
        if not HAS_PSUTIL: return
        try:
            proc = psutil.Process(self.pid)
            try:
                io_counters = proc.io_counters()
                self.peaks['io_read_start'] = io_counters.read_bytes
                self.peaks['io_write_start'] = io_counters.write_bytes
            except (AttributeError, psutil.AccessDenied): pass

            while self.running:
                try:
                    cpu = proc.cpu_percent(interval=0.1) # Sleep de 0.1s acontece aqui
                    if cpu > self.peaks['cpu_percent']: self.peaks['cpu_percent'] = cpu
                except: pass
                try:
                    mem = proc.memory_info().rss / (1024 * 1024)
                    if mem > self.peaks['memory_mb']: self.peaks['memory_mb'] = mem
                except: pass
                if not self.running: break
            
            try:
                io_counters = proc.io_counters()
                self.peaks['io_read_end'] = io_counters.read_bytes
                self.peaks['io_write_end'] = io_counters.write_bytes
            except: pass
        except psutil.NoSuchProcess: pass

    def stop(self):
        self.running = False

    def get_stats(self):
        read_mb = max(0, (self.peaks['io_read_end'] - self.peaks['io_read_start']) / (1024*1024))
        write_mb = max(0, (self.peaks['io_write_end'] - self.peaks['io_write_start']) / (1024*1024))
        return {'cpu': round(self.peaks['cpu_percent'], 1), 'ram': round(self.peaks['memory_mb'], 1), 'read': round(read_mb, 2), 'write': round(write_mb, 2)}

# --- NOVA CLASSE: CODE SAMPLER ---
class CodeSampler(threading.Thread):
    """
    Espião Estatístico: Verifica a cada X ms onde o código está parando.
    Identifica linhas quentes (hot lines) sem overhead massivo.
    """
    def __init__(self, interval=0.01): # 10ms
        super().__init__()
        self.interval = interval
        self.running = True
        self.daemon = True
        self.samples = collections.defaultdict(int) # {(arquivo, linha): contagem}
        self.main_thread_id = threading.main_thread().ident

    def run(self):
        while self.running:
            time.sleep(self.interval)
            try:
                # Pega o frame atual da thread principal
                frame = sys._current_frames().get(self.main_thread_id)
                if frame:
                    # Filtra bibliotecas internas do Python para focar no projeto
                    filename = frame.f_code.co_filename
                    if "doxoade" in filename or os.getcwd() in filename:
                        self.samples[(filename, frame.f_lineno)] += 1
            except Exception:
                pass

    def stop(self):
        self.running = False
        
    def get_hot_lines(self, limit=5):
        # Retorna as 5 linhas mais frequentes
        sorted_lines = sorted(self.samples.items(), key=lambda item: item[1], reverse=True)
        return sorted_lines[:limit]

class ChronosRecorder:
    def __init__(self):
        self.session_uuid = str(uuid.uuid4())
        self.monitor = None
        self.profiler = None
        self.sampler = None # Novo
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

        # 1. Monitor Hardware
        self.monitor = ResourceMonitor(os.getpid())
        self.monitor.start()
        
        # 2. Profiler de Função (cProfile)
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        # 3. Profiler de Linha (Sampler) [NOVO]
        self.sampler = CodeSampler(interval=0.01) # 10ms de resolução
        self.sampler.start()
        
        self.start_timestamp = datetime.now(timezone.utc).isoformat()
        self.full_cmd = " ".join(sys.argv)
        self.work_dir = os.getcwd()

    def end_command(self, exit_code, duration_ms):
        if not self.monitor: return

        # Para monitores
        self.monitor.stop()
        self.sampler.stop() # Para o espião
        
        resources = self.monitor.get_stats()
        hot_lines = self.sampler.get_hot_lines()
        
        # Processa cProfile
        self.profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(15)
        profile_text = s.getvalue()
        
        top_funcs = []
        for line in profile_text.splitlines():
            if "(" in line and ")" in line and os.getcwd() in line:
                top_funcs.append(line.strip())

        # Formata dados das linhas quentes para salvar
        # Formato: [{"file": "...", "line": 10, "hits": 50}, ...]
        line_profile_data = []
        for (fname, lineno), hits in hot_lines:
            # Limpa o caminho para ser relativo ao projeto
            clean_name = fname.replace(os.getcwd(), "").strip(os.sep)
            line_profile_data.append({
                "file": clean_name,
                "line": lineno,
                "hits": hits
            })

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
                json.dumps(line_profile_data) # [NOVO] Salva as linhas
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

chronos_recorder = ChronosRecorder()