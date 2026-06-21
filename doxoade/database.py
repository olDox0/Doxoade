# doxoade/doxoade/database.py
"""
Módulo de Persistência (Sapiens/Chronos) - v71.1.
Gerencia o ciclo de vida do banco de dados e migrações de esquema.
ESTRATÉGIA: Migration Dispatcher para conformidade MPoT-4/17.
"""

import click
import zlib
import json
import time
import os
from pathlib import Path

import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
from doxoade.tools.telemetry_tools.logger import chief_heartbeat

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 134

def get_db_connection():
    """Abre conexão com monitoramento de performance (Sapiens Watcher)."""
    t0 = time.perf_counter()
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # [PLATINUM] Configurações de Performance para o Celeron
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA cache_size=-{4000}") # 4MB de cache em RAM
    
    conn.row_factory = sqlite3.Row
    
    duration = (time.perf_counter() - t0) * 1000
    if duration > 50: # Se levar mais de 50ms para abrir, Hórus avisa
        chief_heartbeat("HADES", "SLOW_CONNECTION", {"ms": round(duration, 2)})
        
    if os.environ.get('DOXOADE_HORUS_ACTIVE') == '1':
        conn.execute("PRAGMA synchronous=FULL")
    else:
        conn.execute("PRAGMA synchronous=NORMAL")
        
    return conn

def _m_v1_v3_core(cursor):
    """Esquema Inicial: Events, Findings e Solutions."""
    cursor.execute('\n    CREATE TABLE IF NOT EXISTS events (\n        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, doxoade_version TEXT,\n        command TEXT NOT NULL, project_path TEXT NOT NULL, execution_time_ms REAL, status TEXT\n    );')
    cursor.execute('\n    CREATE TABLE IF NOT EXISTS findings (\n        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, severity TEXT NOT NULL,\n        message TEXT NOT NULL, details TEXT, file TEXT, line INTEGER, finding_hash TEXT,\n        category TEXT, FOREIGN KEY (event_id) REFERENCES events (id)\n    );')
    cursor.execute('\n    CREATE TABLE IF NOT EXISTS solutions (\n        id INTEGER PRIMARY KEY AUTOINCREMENT, finding_hash TEXT NOT NULL UNIQUE,\n        stable_content TEXT NOT NULL, commit_hash TEXT NOT NULL, project_path TEXT NOT NULL,\n        timestamp TEXT NOT NULL, file_path TEXT NOT NULL, message TEXT, error_line INTEGER\n    );')

def _m_v4_v9_incidents(cursor):
    """Dívida Técnica: Tabela de Incidentes Abertos."""
    cursor.execute("\n    CREATE TABLE IF NOT EXISTS open_incidents (\n        finding_hash TEXT PRIMARY KEY, file_path TEXT NOT NULL,\n        commit_hash TEXT NOT NULL, timestamp TEXT NOT NULL,\n        project_path TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '',\n        line INTEGER, category TEXT\n    );")

def _m_v10_v14_genesis(cursor):
    """Projeto Gênese: IA Simbólica e Templates."""
    cursor.execute("\n    CREATE TABLE IF NOT EXISTS solution_templates (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        problem_pattern TEXT NOT NULL UNIQUE,\n        solution_template TEXT NOT NULL,\n        category TEXT NOT NULL,\n        confidence INTEGER DEFAULT 1,\n        created_at TEXT NOT NULL,\n        type TEXT DEFAULT 'HARDCODED',\n        diff_pattern TEXT\n    );")

def _m_v15_chronos(cursor):
    """Protocolo Chronos: Auditoria de Comandos e Arquivos."""
    cursor.execute('\n    CREATE TABLE IF NOT EXISTS command_history (\n        id INTEGER PRIMARY KEY AUTOINCREMENT, session_uuid TEXT NOT NULL,\n        timestamp TEXT NOT NULL, command_name TEXT NOT NULL,\n        full_command_line TEXT NOT NULL, working_dir TEXT NOT NULL,\n        exit_code INTEGER, duration_ms REAL, cpu_percent REAL DEFAULT 0,\n        peak_memory_mb REAL DEFAULT 0, io_read_mb REAL DEFAULT 0,\n        io_write_mb REAL DEFAULT 0, profile_data TEXT, system_info TEXT,\n        line_profile_data TEXT\n    );')
    cursor.execute('\n    CREATE TABLE IF NOT EXISTS file_audit (\n        id INTEGER PRIMARY KEY AUTOINCREMENT, command_id INTEGER NOT NULL,\n        file_path TEXT NOT NULL, operation_type TEXT NOT NULL,\n        diff_content TEXT, backup_path TEXT,\n        FOREIGN KEY (command_id) REFERENCES command_history (id)\n    );')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cmd_hist_ts ON command_history(timestamp);')

def _m_v19_payloads(cursor):
    """Protocolo de Expansão de Memória: Armazena inputs e outputs comprimidos."""
    try:
        cursor.execute('ALTER TABLE command_history ADD COLUMN compressed_payload BLOB;')
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _m_v19_payloads\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")

def _m_v20_nexus_vault(cursor):
    """Cria a infraestrutura do Cofre de Sessão."""
    # Guarda o hash da senha
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vault_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            salt TEXT
        );
    ''')
    # Guarda o status da sessão atual
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vault_session (
            id INTEGER PRIMARY KEY,
            unlocked_until TEXT, -- Timestamp de expiração
            session_key TEXT
        );
    ''')

def _m_v21_operational_logs(cursor):
    """Cria a infraestrutura de logs operacionais (Heartbeat)."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operational_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            subsystem TEXT NOT NULL,
            action TEXT NOT NULL,
            data TEXT,
            pid INTEGER
        );
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_op_logs_ts ON operational_logs(timestamp);')

def _m_v22_moduloid_acervo(cursor):
    """Infraestrutura para o Acervo Global de Moduloids."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moduloid_acervo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            filename TEXT,
            docstring TEXT,
            capabilities TEXT, -- JSON com lista de funções extraídas
            version INTEGER DEFAULT 1,
            last_updated DATETIME,
            origin_project TEXT
        );
    ''')

def _m_v23_hades_optimization_and_lexicon(cursor):
    """Refactor v23: Índices + Tabela de Acervo."""
    # [OURO] Agora o print aparecerá
    click.secho("⚒️  [HADES] Injetando Motores de Performance e Acervo...", fg='cyan')
    
    # 1. Índices de Elite (Reduzem busca de 21s para 0.05s)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_hash ON findings(finding_hash);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_event ON findings(event_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_path ON events(project_path);')
    
    # 2. Tabela de Acervo (Knowledge Lexicon)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_lexicon (
            finding_hash TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            category TEXT,
            first_seen TEXT,
            last_seen TEXT,
            occurrence_count INTEGER DEFAULT 1,
            solution_id INTEGER,
            tags TEXT,
            FOREIGN KEY (solution_id) REFERENCES solutions(id)
        );
    ''')
    cursor.execute('ANALYZE;')

def _m_v24_lexicon_expansion(cursor):
    """Expande o Lexicon para suportar exemplos de código (Acervo)."""
    # Adiciona colunas para armazenar os fragmentos de código
    try:
        cursor.execute('ALTER TABLE knowledge_lexicon ADD COLUMN snippet_broken TEXT;')
        cursor.execute('ALTER TABLE knowledge_lexicon ADD COLUMN snippet_fixed TEXT;')
        cursor.execute('ALTER TABLE knowledge_lexicon ADD COLUMN diff_patch TEXT;')
    except Exception as e: print(e)
    
def _m_v132_lexicon_expansion(cursor):
    """Expande o Lexicon para suportar exemplos de código e metadados."""
    click.secho("💎 [HADES] Expandindo Córtex de Conhecimento...", fg='cyan')
    # Adiciona colunas para o "Antes e Depois"
    cols = [
        ('knowledge_lexicon', 'snippet_broken', 'TEXT'),
        ('knowledge_lexicon', 'snippet_fixed', 'TEXT'),
        ('knowledge_lexicon', 'diff_patch', 'TEXT')
    ]
    for table, col, col_type in cols:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type};')
        except sqlite3.OperationalError: pass

def _m_v134_incident_schema_repair(cursor):
    """Garante que a tabela de incidentes seja resiliente."""
    # Como o SQLite não permite ALTER COLUMN facilmente, garantimos o índice
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_hash ON open_incidents(finding_hash);')


def _apply_incremental_patches(cursor, current_version):
    """Aplica alterações de colunas em tabelas existentes (Resiliência)."""
    alterations = [(2, 'ALTER TABLE findings ADD COLUMN category TEXT;'), (6, "ALTER TABLE solutions ADD COLUMN message TEXT NOT NULL DEFAULT '';"), (12, 'ALTER TABLE open_incidents ADD COLUMN category TEXT;')]
    for ver, sql in alterations:
        if current_version < ver:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

def _log_execution(command_name, path, results, arguments, execution_time_ms, exit_code=0):
    start_persistence_worker()
    from datetime import datetime, timezone
    import uuid

    # 1. Prepara o Payload Denso (Input + Output real)
    payload_data = {
        "input": {
            "cwd": os.path.abspath(path),
            "args": arguments,
            "full_argv": sys.argv
        },
        "output": {
            "findings": results.get('findings', []), # Guarda TODOS os problemas, não só o resumo
            "summary": results.get('summary', {})
        }
    }
    
    # 2. Compactação Nexus (Nível 6 - Equilíbrio CPU/Tamanho)
    json_bytes = json.dumps(payload_data).encode('utf-8')
    compressed = zlib.compress(json_bytes, level=6)

    # 3. Inserção no Banco
    _ts = datetime.now(timezone.utc).isoformat()
    _session = uuid.uuid4().hex
    
    _query = '''
        INSERT INTO command_history 
        (session_uuid, timestamp, command_name, full_command_line, working_dir, exit_code, duration_ms, compressed_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    _params = (
        _session, _ts, command_name, " ".join(sys.argv), 
        os.path.abspath(path), exit_code, execution_time_ms, compressed
    )
    
    _LOG_QUEUE.put((_query, _params))

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);')
        res = cursor.execute('SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;').fetchone()
        current_version = res[0] if res else 0

        if current_version < DB_VERSION:
            click.secho(f"🔧 [SAPIENS] Migrando base v{current_version} -> v{DB_VERSION}...", fg='yellow')
            
            # [PLATINUM FIX] Agora o gatilho é maior que 120
            if current_version < 131: 
                _m_v23_hades_optimization_and_lexicon(cursor)
            if current_version < 132:     
                _m_v24_lexicon_expansion(cursor)
            if current_version < 133:
                _m_v132_lexicon_expansion(cursor)
            if current_version < 134:
                _m_v134_incident_schema_repair
            
            # [REFORÇO] Garante colunas sistêmicas
            repair_cols = [
                ('findings', 'category', 'TEXT'),
                ('open_incidents', 'category', 'TEXT'),
                ('open_incidents', 'severity', 'TEXT'), # <<-- O FIX PARA O SEU CRASH
                ('command_history', 'compressed_payload', 'BLOB')
            ]
            for table, col, col_type in repair_cols:
                try:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type};')
                except sqlite3.OperationalError: pass

            cursor.execute('DELETE FROM schema_version;')
            cursor.execute('INSERT INTO schema_version (version) VALUES (?);', (DB_VERSION,))
            conn.commit()
            click.secho(f"✅ [HADES] Cérebro atualizado para v{DB_VERSION}.", fg='green', bold=True)
    except Exception as e:
        conn.rollback()
        click.secho(f"✘ [FALHA] Erro estrutural: {e}", fg='red')
    finally:
        conn.close()
        
def get_db_stats():
    """Retorna métricas vitais de saúde do banco (Hades Sentry)."""
    conn = get_db_connection()
    stats = {}
    try:
        # 1. Integridade e Fragmentação
        stats['integrity'] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        stats['page_count'] = conn.execute("PRAGMA page_count").fetchone()[0]
        stats['page_size'] = conn.execute("PRAGMA page_size").fetchone()[0]
        stats['freelist_count'] = conn.execute("PRAGMA freelist_count").fetchone()[0]
        
        # 2. Peso Físico
        stats['size_mb'] = round((stats['page_count'] * stats['page_size']) / (1024 * 1024), 2)
        # Porcentagem de "lixo" (espaço que pode ser recuperado com VACUUM)
        stats['bloat_pct'] = round((stats['freelist_count'] / stats['page_count']) * 100, 2) if stats['page_count'] > 0 else 0

        # 3. Censo de Registros
        tables = ['events', 'findings', 'command_history', 'knowledge_lexicon']
        stats['counts'] = {}
        for t in tables:
            try:
                stats['counts'][t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                from traceback import print_tb as exc_trace
                exc_obj, exc_tb = _dox_sys.exc_info()
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                exc_trace(exc_tb)
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_db_stats\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            
    finally:
        conn.close()
    return stats

def optimize_database():
    """Executa a purificação física e lógica (Hades Purge)."""
    conn = get_db_connection()
    try:
        click.secho("🧹 [HADES] Iniciando compactação e recalibração...", fg='cyan')
        # Limpa espaços vazios e reorganiza o arquivo no disco
        conn.execute("VACUUM")
        # Recalcula estatísticas para o Query Planner do Celeron
        conn.execute("ANALYZE")
        return True
    except Exception as e:
        click.echo(f"Erro na otimização: {e}")
        return False
    finally:
        conn.close()