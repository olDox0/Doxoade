# -*- coding: utf-8 -*-
# doxoade/tools/alexandria/engine.py
"""
Alexandria Engine v4.0 — Motor de Persistência Assíncrona Nexus.
Otimizado: Batch Ingest, Idle Timeout adaptativo (100ms) e Zero Lock Contention.
"""
from __future__ import annotations

import os
import queue
import sqlite3
import threading
from pathlib import Path


class AlexandriaEngine:
    def __init__(self):
        self.queue = queue.Queue()
        self._thread = None
        self._idle_timeout = 0.1  # 🛑 OTIMIZAÇÃO: 100ms em vez de 5.0s
        self._lock = threading.Lock()

    def enqueue(self, query, params=()):
        self.queue.put((query, params))
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, daemon=True)
                self._thread.start()

    def _init_db_structure(self, cursor: sqlite3.Cursor):
        """Garante a estrutura unificada de logs sem invalidar caches do SQLite."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operational_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subsystem TEXT,
                action TEXT,
                data TEXT,
                pid INTEGER,
                level TEXT,
                message TEXT,
                details TEXT
            )
        """)

        cursor.execute("PRAGMA table_info(operational_logs)")
        colunas_existentes = {info[1] for info in cursor.fetchall()}
        
        colunas_modernas = [
            ("subsystem", "TEXT"),
            ("action", "TEXT"),
            ("data", "TEXT"),
            ("pid", "INTEGER"),
            ("level", "TEXT"),
            ("message", "TEXT"),
            ("details", "TEXT")
        ]
        
        for nome_coluna, tipo_coluna in colunas_modernas:
            if nome_coluna not in colunas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE operational_logs ADD COLUMN {nome_coluna} {tipo_coluna}")
                except sqlite3.OperationalError:
                    pass

    def _worker(self):
        from doxoade.tools.core_locator import GLOBAL_DB_FILE, GLOBAL_DATA_DIR
        
        GLOBAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        os.makedirs(os.path.dirname(str(GLOBAL_DB_FILE)), exist_ok=True)

        # Conexão direta com WAL e timeout resiliente
        conn = sqlite3.connect(str(GLOBAL_DB_FILE), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        cursor = conn.cursor()

        self._init_db_structure(cursor)
        conn.commit()

        while True:
            try:
                # 🛑 Aguarda com timeout curto e drena em lote
                task = self.queue.get(timeout=self._idle_timeout)
                if task is None:
                    break

                batch = [task]
                # Coleta todos os itens já acumulados na fila de uma vez só
                while not self.queue.empty() and len(batch) < 50:
                    try:
                        batch.append(self.queue.get_nowait())
                    except queue.Empty:
                        break

                # 🛑 GRAVAÇÃO ATÔMICA EM LOTE: Um único commit para todo o lote!
                try:
                    cursor.execute("BEGIN TRANSACTION")
                    for q, p in batch:
                        cursor.execute(q, p)
                    conn.commit()
                except sqlite3.OperationalError as e:
                    conn.rollback()
                    # Fallback com re-verificação de colunas se houver divergência
                    if "no such column" in str(e) or "has no column" in str(e):
                        self._init_db_structure(cursor)
                        cursor.execute("BEGIN TRANSACTION")
                        for q, p in batch:
                            cursor.execute(q, p)
                        conn.commit()
                    else:
                        raise e

                for _ in batch:
                    self.queue.task_done()

            except queue.Empty:
                # Fila vazia após 100ms de inatividade: encerra a thread de forma limpa
                break
            except Exception as e:
                # Falha pontual nunca derruba o processo
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

        conn.close()


alexandria = AlexandriaEngine()


def alexandria_write(query, params=()):
    alexandria.enqueue(query, params)
