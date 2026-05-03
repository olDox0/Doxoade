# doxoade/doxoade/tools/db_utils.py
"""
Utilitários de Banco de Dados com Persistência Assíncrona.
Resolve o gargalo de latência (Hot Line) via Async Buffer Pattern.
"""
import threading
import queue
import os
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
            if item is None:
                break
            batch_buffer.append(item)
            if len(batch_buffer) >= 50:
                for query, params in batch_buffer:
                    cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
        except queue.Empty:
            if batch_buffer:
                for query, params in batch_buffer:
                    cursor.execute(query, params)
                conn.commit()
                batch_buffer = []
            continue
    if batch_buffer:
        for query, params in batch_buffer:
            cursor.execute(query, params)
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
        _LOG_QUEUE.put(None)
        _WORKER_THREAD.join(timeout=3.0)
        _WORKER_THREAD = None

def _log_execution(command_name, path, results, arguments, execution_time_ms, exit_code=0):
    """
    Sincroniza o log com a tabela command_history (Protocolo Chronos).
    """
    start_persistence_worker() 
    
    from datetime import datetime, timezone
    import json
    import uuid
    import sys

    _ts = datetime.now(timezone.utc).isoformat()
    _p_abs = os.path.abspath(path)
    _session = uuid.uuid4().hex
    
    # Consolida metadados para a coluna system_info
    sys_info_dict = {
        "args": arguments,
        "summary": results.get('summary', {}),
        "shell": os.environ.get('SHELL', 'cmd.exe' if os.name == 'nt' else 'unknown')
    }
    _sys_info = json.dumps(sys_info_dict)

    # Query para a tabela command_history (a que o timeline realmente lê)
    _query = '''
        INSERT INTO command_history 
        (session_uuid, timestamp, command_name, full_command_line, working_dir, exit_code, duration_ms, system_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    # Tenta capturar a linha de comando completa do sistema
    _full_cmd = " ".join(sys.argv)
    
    _params = (
        _session, _ts, command_name, _full_cmd, 
        _p_abs, exit_code, execution_time_ms, _sys_info
    )
    
    # Envia para a fila de persistência do Hades
    _LOG_QUEUE.put((_query, _params))

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
    current_hashes = [f.get('finding_hash') for f in findings if isinstance(f, dict) and f.get('finding_hash')]
    if current_hashes:
        placeholders = ', '.join(['?'] * len(current_hashes))
        cursor.execute(f'DELETE FROM open_incidents WHERE project_path = ? AND finding_hash NOT IN ({placeholders})', (project_path_abs, *current_hashes))
    else:
        cursor.execute('DELETE FROM open_incidents WHERE project_path = ?', (project_path_abs,))
    from datetime import datetime, timezone
    for f in findings:
        if not isinstance(f, dict) or not f.get('finding_hash'):
            continue
        cursor.execute('\n            INSERT OR REPLACE INTO open_incidents \n            (finding_hash, file_path, line, message, severity, category, project_path, timestamp)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n        ', (f['finding_hash'], f.get('file'), f.get('line'), f.get('message'), f.get('severity'), f.get('category'), project_path_abs, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    
def encrypt_payload(data_bytes, password):
    # Lógica simplificada de XOR com Hash para manter Silo sem dependências externas (como cryptography)
    # Para segurança máxima profissional, o ideal seria 'pip install cryptography'
    key = hashlib.sha256(password.encode()).digest()
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data_bytes)])

# No momento de gravar:
#if vault_is_active:
#    final_blob = encrypt_payload(compressed_data, current_session_password)
#else:
#    final_blob = compressed_data # Ou bloqueia a gravação
