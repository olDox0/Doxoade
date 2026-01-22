# doxoade/tools/db_utils.py
"""
Utilitários de Banco de Dados com Persistência Assíncrona.
Resolve o gargalo de latência (Hot Line) via Async Buffer Pattern.
"""
import threading
import queue
import sys
import os
# [DOX-UNUSED] import sqlite3
from datetime import datetime, timezone

# --- INFRAESTRUTURA ASYNC ---
_LOG_QUEUE = queue.Queue()
_WORKER_THREAD = None
_STOP_EVENT = threading.Event()

def _db_worker():
    """Consumidor: Processa a fila de escrita em background."""
    from doxoade.database import get_db_connection
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        while not _STOP_EVENT.is_set() or not _LOG_QUEUE.empty():
            try:
                item = _LOG_QUEUE.get(timeout=0.5)
                if item is None: break
                
                query, params = item
                cursor.execute(query, params)
                conn.commit()
                _LOG_QUEUE.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                sys.stderr.write(f"\n[INTERNAL-ERROR] Falha na persistência assíncrona: {e}\n")
    finally:
        if conn: conn.close()

def start_persistence_worker():
    """Inicia a thread de fundo."""
    global _WORKER_THREAD
    if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
        _STOP_EVENT.clear()
        _WORKER_THREAD = threading.Thread(target=_db_worker, daemon=True, name="DoxoLogWorker")
        _WORKER_THREAD.start()

def stop_persistence_worker():
    """Garante que o buffer seja esvaziado antes de fechar."""
    _STOP_EVENT.set()
    _LOG_QUEUE.put(None)
    if _WORKER_THREAD:
        _WORKER_THREAD.join(timeout=2.0)

# --- PRODUTORES (APIs Públicas) ---

def _log_execution(command_name, path, results, arguments, execution_time_ms=0):
    """Registra evento de execução (Assíncrono)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    project_path_abs = os.path.abspath(path)
    
    query = """
        INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (timestamp, "63.2", command_name, project_path_abs, round(execution_time_ms, 2), "completed")
    _LOG_QUEUE.put((query, params))

def _update_open_incidents(logger_results, project_path):
    """
    Sincroniza o estado atual do linter com o banco de dados.
    Blindagem MPoT-7: Resiliente a resultados não-estruturados (strings).
    """
    from doxoade.database import get_db_connection
    from datetime import datetime, timezone
    import os
    
    # Validação de Entrada: Se não for uma lista, não há o que processar
    if not isinstance(logger_results, list):
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    project_path_abs = os.path.abspath(project_path)

    # 1. Extração segura de hashes (Ignora itens que não são dicionários)
    current_finding_hashes = []
    for f in logger_results:
        if isinstance(f, dict) and f.get('finding_hash'):
            current_finding_hashes.append(f.get('finding_hash'))

    # 2. Fecha incidentes que sumiram do radar (Resolvidos)
    if current_finding_hashes:
        placeholders = ', '.join(['?'] * len(current_finding_hashes))
        query_del = f"DELETE FROM open_incidents WHERE project_path = ? AND finding_hash NOT IN ({placeholders})"
        cursor.execute(query_del, (project_path_abs, *current_finding_hashes))
    else:
        # Se a lista de hashes está vazia, pode significar que todos foram corrigidos 
        # OU que o resultado foi apenas uma string informativa.
        # Só deletamos tudo se logger_results estiver vazio ou for explicitamente [].
        if len(logger_results) == 0:
            cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path_abs,))

    # 3. Upsert de incidentes estruturados
    for finding in logger_results:
        # Pula se o item for uma string informativa (ex: "No files found")
        if not isinstance(finding, dict):
            continue
            
        f_hash = finding.get('finding_hash')
        if not f_hash: 
            continue
        
        # SQL para manter a data da primeira vez que o erro foi visto
        cursor.execute("""
            INSERT OR REPLACE INTO open_incidents 
            (finding_hash, file_path, line, message, severity, category, project_path, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT first_seen FROM open_incidents WHERE finding_hash = ?), ?))
        """, (
            f_hash, finding.get('file', 'unknown'), finding.get('line', 0), 
            finding.get('message', 'No message'), finding.get('severity', 'WARNING'), 
            finding.get('category', 'UNCATEGORIZED'), project_path_abs,
            f_hash, datetime.now(timezone.utc).isoformat()
        ))

    conn.commit()
    conn.close()