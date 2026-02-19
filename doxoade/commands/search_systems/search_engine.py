# -*- coding: utf-8 -*-
"""Motor Nexus Search - Casa de Máquinas (MPoT-17)."""
import os
# [DOX-UNUSED] import subprocess
from pathlib import Path

from .search_state import SearchState
from ...tools.streamer import ufs
from ...tools.vulcan.bridge import vulcan_bridge

def run_search_engine(state: SearchState, filters: dict):
    """Orquestra a busca multidimensional (v91.1)."""
    q = state.query
    limit = state.limit
    # Normalização de path para SQL no Windows
    path_filter = os.getcwd().replace('\\', '/').lower() if filters.get('here') else None

    # 1. Código Local
    if filters.get('run_code'):
        state.matches = _search_code_logic(Path(state.root), q, limit)

    # 2. Timeline
    if filters.get('run_time'):
        state.timeline = _search_timeline_logic(q, limit, path_filter)

    # 3. Banco de Dados
    if filters.get('run_db'):
        state.db_results = _search_database_logic(q, limit, path_filter)

    # 4. Git
    if filters.get('commits'):
        from .search_utils import _handle_git_search
        state.git_results = _handle_git_search(q, limit)

# --- MOTORES PRIVADOS ---

def _search_code_logic(root: Path, query: str, limit: int) -> list:
    matches = []
    q_lower = query.lower()
    q_bytes = query.encode('utf-8')
    
    QUARANTINE = {'.git', 'venv', '__pycache__', 'build', 'dist', '.doxoade', '.doxoade_cache'}
    
    # Busca por acelerador Vulcano específico para busca
    # O Bridge agora busca por assinaturas de "vulcan_search"
    v_mod = vulcan_bridge.get_optimized_module("vulcan_search")

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in QUARANTINE]
        for filename in files:
            file_path = Path(r) / filename
            if file_path.suffix not in {'.py', '.md', '.txt', '.dox', '.toml'}: continue
            
            try:
                # ESTRATÉGIA DE VELOCIDADE (PASC-6.4)
                if v_mod and hasattr(v_mod, 'scan_buffer_with_lines'):
                    raw_data = ufs.get_raw_content(str(file_path))
                    # O Vulcan agora retorna (offset, line_num)
                    hits = v_mod.scan_buffer_with_lines(raw_data, q_bytes)
                    
                    if hits:
                        content_str = raw_data.decode('utf-8', 'ignore')
                        lines_cache = content_str.splitlines() # Split uma única vez por arquivo
                        for off, line_n in hits:
                            if line_n <= len(lines_cache):
                                matches.append({
                                    'file': str(file_path.relative_to(root)),
                                    'line': line_n, 
                                    'text': lines_cache[line_n-1].strip(), 
                                    'type': file_path.suffix
                                })
                            if len(matches) >= limit: return matches
                else:
                    # 2. MODO FALLBACK (Line-Scan Python)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if q_lower in line.lower():
                                matches.append({
                                    'file': str(file_path.relative_to(root)),
                                    'line': i, 'text': line.strip(), 'type': file_path.suffix
                                })
                                if len(matches) >= limit: return matches
            except Exception as e:
                print(f"\033[0;33m _search_code_logic - Exception: {e}")
                continue
    return matches

def _search_database_logic(query, limit, path_filter) -> dict:
    from ...database import get_db_connection
    from sqlite3 import Row
    res = {'incidents': [], 'solutions': []}
    conn = get_db_connection()
    conn.row_factory = Row
    sql_q = f"%{query}%"
    
    try:
        cursor = conn.cursor()
        # Incidentes
        inc_sql = "SELECT * FROM open_incidents WHERE (message LIKE ? OR file_path LIKE ?)"
        params = [sql_q, sql_q]
        if path_filter:
            inc_sql += " AND project_path LIKE ?"
            params.append(f"%{path_filter}%")
        
        cursor.execute(inc_sql + " LIMIT ?", params + [limit])
        for row in cursor.fetchall():
            res['incidents'].append({'file': row['file_path'], 'line': row['line'], 'message': row['message'], 'category': row['category']})
        
        # Soluções (Gênese)
        sol_sql = "SELECT * FROM solutions WHERE (message LIKE ? OR file_path LIKE ?)"
        sol_params = [sql_q, sql_q]
        if path_filter:
            sol_sql += " AND project_path LIKE ?"
            sol_params.append(f"%{path_filter}%")
            
        cursor.execute(sol_sql + " LIMIT ?", sol_params + [limit])
        for row in cursor.fetchall():
            res['solutions'].append({'file': row['file_path'], 'message': row['message']})
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
    finally: conn.close()
    return res

def _search_timeline_logic(query, limit, path_filter) -> list:
    from ...database import get_db_connection
    from sqlite3 import Row
    results = []
    conn = get_db_connection()
    conn.row_factory = Row
    sql_q = f"%{query}%"
    
    q = "SELECT * FROM command_history WHERE full_command_line LIKE ?"
    params = [sql_q]
    if path_filter:
        q += " AND working_dir LIKE ?"
        params.append(f"%{path_filter}%")
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
        if not cursor.fetchone(): return []
        
        cursor.execute(q + " ORDER BY id DESC LIMIT ?", params + [limit])
        for row in cursor.fetchall():
            results.append({
                'full_line': row['full_command_line'], 
                'dir': row['working_dir'], 
                'timestamp': row['timestamp'], 
                'exit_code': row['exit_code']
            })
    except Exception as e:
        print(f"\033[0;33m _search_timeline_logic - Exception: {e}")
    finally: conn.close()
    return results