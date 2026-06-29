# -*- coding: utf-8 -*-
# doxoade/tools/templates/vulcan/embedded_latest.py
from functools import wraps
from pathlib import Path
import sys
import os
import re
from click import echo
import importlib.util
import importlib.machinery
import time
import atexit
import json
import uuid
import datetime
import threading
import collections

# Importação Segura do NexusDB (Aegis Layer)
try:
    import doxoade.tools.aegis.nexus_db as sqlite3
except ImportError:
    import sqlite3

# ── Configurações de Telemetria ──────────────────────────────────────────────
_cl_boot_time = time.monotonic()
_cl_peaks = {'cpu': 0.0, 'ram_mb': 0.0, 'io_r_base': 0, 'io_w_base': 0}

# ── Monitor de Recursos (Dionísio) ───────────────────────────────────────────
class _ChronosLiteMonitor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._running = True
    def run(self):
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            while self._running:
                cpu = proc.cpu_percent(interval=None)
                ram = proc.memory_info().rss / (1024 * 1024)
                if cpu > _cl_peaks['cpu']:    _cl_peaks['cpu'] = cpu
                if ram > _cl_peaks['ram_mb']: _cl_peaks['ram_mb'] = ram
                time.sleep(0.3)
        except Exception: pass
    def stop(self): self._running = False

_cl_monitor = _ChronosLiteMonitor()
_cl_monitor.start()

# ── Resolutor de Caminhos (Hades) ────────────────────────────────────────────
def _find_project_root(path):
    curr = Path(path).resolve()
    for parent in [curr, *curr.parents]:
        if (parent / ".doxoade").exists(): return parent
    return None

def _dump_vulcan_telemetry():
    """Sincroniza telemetria com o Database em data/doxoade.db."""
    _cl_monitor.stop()
    duration_ms = (time.monotonic() - _cl_boot_time) * 1000
    script_file = sys.argv[0] if sys.argv else "unknown"
    root = _find_project_root(script_file)
    
    _root = _find_project_root(script_file)
    try:
        from doxoade.core_database import DB_FILE
        db_path = Path(DB_FILE)
    except (ImportError, AttributeError):
        db_path = Path.home() / '.doxoade' / 'doxoade.db'
    
    if not db_path: raise RuntimeError(f"db_path tem caminho quebrado {db_path}")
    
    try:
        with sqlite3.connect(str(db_path), timeout=10.0) as conn:
            conn.execute("""
                INSERT INTO command_history 
                (session_uuid, timestamp, command_name, full_command_line, working_dir,
                 exit_code, duration_ms, cpu_percent, peak_memory_mb, system_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), datetime.datetime.now().isoformat(),
                "vulcan_ext_" + Path(script_file).stem, " ".join(sys.argv),
                os.getcwd(), 0, round(duration_ms, 1), 
                _cl_peaks['cpu'], _cl_peaks['ram_mb'],
                json.dumps({"note": "Vulcan Ext", "root": str(root)})
            ))
    except Exception: pass

atexit.register(_dump_vulcan_telemetry)