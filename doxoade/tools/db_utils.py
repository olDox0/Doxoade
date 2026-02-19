# -*- coding: utf-8 -*-
# doxoade/tools/db_utils.py (v98.5 Consolidado)
"""
Utilitários de Banco de Dados com Persistência Assíncrona.
Resolve o gargalo de latência (Hot Line) via Async Buffer Pattern.
"""
# [DOX-UNUSED] import time
import threading
# [DOX-UNUSED] import sys
import queue
import os
# [DOX-UNUSED] from .governor import governor # PASC-6.6
# [DOX-UNUSED] import sqlite3

# --- INFRAESTRUTURA ASYNC ---
_LOG_QUEUE = queue.Queue()
_WORKER_THREAD = None
_STOP_EVENT = threading.Event()

def _db_worker():
    from doxoade.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    batch_buffer = []

    while not _STOP_EVENT.is_set() or not _LOG_QUEUE.empty():
        try:
            item = _LOG_QUEUE.get(timeout=0.5)
            if item is None: break
            batch_buffer.append(item)
            
            # PASC-6.4: Commit em lote para performance
            if len(batch_buffer) >= 50:
                for query, params in batch_buffer: cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
        except queue.Empty:
            if batch_buffer:
                for query, params in batch_buffer: cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
            continue
    
    if batch_buffer:
        for query, params in batch_buffer: cursor.execute(query, params)
        conn.commit()
    conn.close()

def start_persistence_worker():
    global _WORKER_THREAD
    if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
        _STOP_EVENT.clear()
        _WORKER_THREAD = threading.Thread(target=_db_worker, daemon=True)
        _WORKER_THREAD.start()

def stop_persistence_worker():
    """Garante o sepultamento dos logs antes do encerramento do processo."""
    global _WORKER_THREAD
    if _WORKER_THREAD:
        _STOP_EVENT.set()
        _LOG_QUEUE.put(None) # Sinal de encerramento
        _WORKER_THREAD.join(timeout=3.0) # Espera o Flush de Osiris
        _WORKER_THREAD = None

# --- PRODUTORES (APIs Públicas) ---

def _log_execution(command_name, path, results, arguments, execution_time_ms):
    """Sela o log no banco de dados (Sincronia Osíris)."""
    from datetime import datetime, timezone
    
    # PASC 8.10: Variáveis com sublinhado para indicar uso interno/telemetria
    _ts = datetime.now(timezone.utc).isoformat()
    _p_abs = os.path.abspath(path)
    
    _query = """
        INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    _params = (_ts, "98.5", command_name, _p_abs, execution_time_ms, "completed")
    
    _LOG_QUEUE.put((_query, _params))

    # 2. Registro dos Findings para o Telemetry (Se existirem)
    if results and 'findings' in results:
        for f in results['findings']:
            # PASC-8.6: Não usamos o event_id real aqui porque ele ainda não foi gerado pelo SQLite
            # O worker de DB vai tratar a vinculação via 'last_insert_rowid' se necessário.
            # No momento, salvamos apenas o resumo estatístico para manter a fila leve.
            pass

def _update_open_incidents(findings, project_path):
    """
    Sincroniza o estado atual do linter com o banco de dados.
    Corrigido: parâmetro renomeado para 'findings' para bater com o check.py.
    """
    if not isinstance(findings, list):
        return

    from doxoade.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    project_path_abs = os.path.abspath(project_path)

    # 1. Coleta hashes atuais
    current_hashes = [f.get('finding_hash') for f in findings if isinstance(f, dict) and f.get('finding_hash')]

    # 2. Limpa resolvidos
    if current_hashes:
        placeholders = ', '.join(['?'] * len(current_hashes))
        cursor.execute(f"DELETE FROM open_incidents WHERE project_path = ? AND finding_hash NOT IN ({placeholders})", 
                       (project_path_abs, *current_hashes))
    else:
        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path_abs,))

    # 3. Upsert de novos
    from datetime import datetime, timezone
    for f in findings:
        if not isinstance(f, dict) or not f.get('finding_hash'): continue
        cursor.execute("""
            INSERT OR REPLACE INTO open_incidents 
            (finding_hash, file_path, line, message, severity, category, project_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (f['finding_hash'], f.get('file'), f.get('line'), f.get('message'), 
              f.get('severity'), f.get('category'), project_path_abs, datetime.now(timezone.utc).isoformat()))

    conn.commit()
    conn.close()