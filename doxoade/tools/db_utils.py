# doxoade/tools/db_utils.py
import os
import sqlite3
from datetime import datetime, timezone
from doxoade.database import get_db_connection
from .git import _run_git_command
from .filesystem import _is_path_ignored

def _log_execution(command_name, path, results, arguments, execution_time_ms=0):
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    project_path_abs = os.path.abspath(path)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status) VALUES (?, ?, ?, ?, ?, ?)", (timestamp, "63.1", command_name, project_path_abs, round(execution_time_ms, 2), "completed"))
        event_id = cursor.lastrowid
        for finding in results.get('findings', []):
            file_path = finding.get('file')
            file_rel = os.path.relpath(file_path, project_path_abs) if file_path and os.path.isabs(file_path) else file_path
            cursor.execute(
                "INSERT INTO findings (event_id, severity, message, details, file, line, finding_hash, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, finding.get('severity'), finding.get('message'), finding.get('details'), file_rel, finding.get('line'), finding.get('hash'), finding.get('category'))
            )
        conn.commit()
    except sqlite3.Error: pass
    finally:
       if conn: conn.close()

def _update_open_incidents(logger_results, project_path):
    findings = logger_results.get('findings', [])
    commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True) or "N/A"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM open_incidents WHERE project_path = ?", (project_path,))
        
        if not findings:
            conn.commit()
            return

        incidents_to_add = []
        processed_hashes = set()
        
        for f in findings:
            finding_hash = f.get('hash')
            file_path = f.get('file')
            
            if not finding_hash or not file_path: continue
            
            if _is_path_ignored(os.path.abspath(os.path.join(project_path, file_path)), project_path):
                continue
            
            if finding_hash in processed_hashes: continue
            processed_hashes.add(finding_hash)
            
            incidents_to_add.append((
                finding_hash, file_path.replace('\\', '/'), f.get('line'),
                f.get('message', ''), f.get('category', 'UNCATEGORIZED'),
                commit_hash, datetime.now(timezone.utc).isoformat(), project_path
            ))
        
        if incidents_to_add:
            cursor.executemany("""
                INSERT INTO open_incidents 
                (finding_hash, file_path, line, message, category, commit_hash, timestamp, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, incidents_to_add)
            
        conn.commit()
    finally:
        conn.close()