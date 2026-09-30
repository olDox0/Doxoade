# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_debug_logger.py
"""
🔬 MESH DEBUG LOGGER — Coleta Estruturada de Dados de Diagnóstico.
Gera JSONL com timeline de eventos, falhas e métricas para análise forense.
"""
from __future__ import annotations
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from collections import deque

class MeshDebugLogger:
    """Logger estruturado com ring buffer e exportação JSON."""

    def __init__(self, max_events: int = 500):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.debug_dir = self.doxoade_dir / "mesh_debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.debug_dir / "mesh_debug.jsonl"
        self._buffer: deque = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._session_start = time.time()
        self._counters = {"sends_attempted": 0, "sends_ok": 0, "sends_failed": 0, "timeouts": 0}

    def event(self, category: str, msg: str, **data):
        entry = {
            "ts": datetime.now().isoformat(),
            "uptime_s": round(time.time() - self._session_start, 2),
            "category": category, "msg": msg, **data
        }
        with self._lock:
            self._buffer.append(entry)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def counter(self, key: str, delta: int = 1):
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + delta
