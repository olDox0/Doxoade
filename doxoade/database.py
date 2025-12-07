# doxoade/database.py
import sqlite3
from pathlib import Path
import click

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 15  # Incrementado para forçar re-verificação

def get_db_connection():
    """Cria o diretório se necessário e retorna uma conexão com o banco de dados."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Cria e/ou migra o esquema do banco de dados para a versão mais recente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);")
        
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO schema_version (version) VALUES (0);")

        cursor.execute("SELECT version FROM schema_version;")
        current_version_row = cursor.fetchone()
        current_version = current_version_row['version'] if current_version_row else 0

        if current_version >= DB_VERSION:
            return

        click.echo(f"Atualizando esquema do banco de dados de v{current_version} para v{DB_VERSION}...")

        # Migração para a Versão 1
        if current_version < 1:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, doxoade_version TEXT,
                command TEXT NOT NULL, project_path TEXT NOT NULL, execution_time_ms REAL, status TEXT
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, severity TEXT NOT NULL,
                message TEXT NOT NULL, details TEXT, file TEXT, line INTEGER, finding_hash TEXT,
                FOREIGN KEY (event_id) REFERENCES events (id)
            );
            """)

        # Migração para a Versão 2
        if current_version < 2:
            try:
                cursor.execute("ALTER TABLE findings ADD COLUMN category TEXT;")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e): raise e

        # Migração para a Versão 3
        if current_version < 3:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, finding_hash TEXT NOT NULL UNIQUE,
                resolution_diff TEXT NOT NULL, commit_hash TEXT NOT NULL, project_path TEXT NOT NULL,
                timestamp TEXT NOT NULL, file_path TEXT NOT NULL
            );
            """)
        
        # Migração para a Versão 4
        if current_version < 4:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_incidents (
                finding_hash TEXT PRIMARY KEY, file_path TEXT NOT NULL,
                commit_hash TEXT NOT NULL, timestamp TEXT NOT NULL
            );
            """)

        if current_version < 5:
            try:
                cursor.execute("ALTER TABLE open_incidents ADD COLUMN project_path TEXT NOT NULL DEFAULT '';")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e): raise e

        if current_version < 6:
            click.echo("Atualizando esquema v6 (adicionando 'message' a solutions)...")
            try:
                cursor.execute("ALTER TABLE solutions ADD COLUMN message TEXT NOT NULL DEFAULT '';")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e): raise e
        
        if current_version < 7:
            click.echo("Atualizando esquema v7 (adicionando 'message' a incidentes)...")
            try:
                cursor.execute("ALTER TABLE open_incidents ADD COLUMN message TEXT NOT NULL DEFAULT '';")
            except sqlite3.OperationalError: pass

        if current_version < 8:
            click.echo("Atualizando esquema v8 (de diff para stable_content)...")
            try:
                cursor.execute("ALTER TABLE solutions RENAME COLUMN resolution_diff TO stable_content;")
                cursor.execute("ALTER TABLE solutions ADD COLUMN error_line INTEGER;")
            except sqlite3.OperationalError:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS solutions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, finding_hash TEXT NOT NULL UNIQUE,
                        stable_content TEXT NOT NULL, commit_hash TEXT NOT NULL, project_path TEXT NOT NULL,
                        timestamp TEXT NOT NULL, file_path TEXT NOT NULL, message TEXT, error_line INTEGER
                    );
                """)

        if current_version < 9:
            click.echo("Atualizando esquema v9 (adicionando 'line' a incidentes)...")
            try:
                cursor.execute("ALTER TABLE open_incidents ADD COLUMN line INTEGER;")
            except sqlite3.OperationalError: pass

        # Migração para a Versão 10 - CORRIGIDA
        if current_version < 10:
            click.echo("Atualizando esquema v10 (Projeto Gênese: Tabela de Templates)...")
            # Primeiro, verifica se a tabela existe e se tem a estrutura correta
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='solution_templates'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # Verifica se a coluna problem_pattern existe
                cursor.execute("PRAGMA table_info(solution_templates)")
                columns = {row['name'] for row in cursor.fetchall()}
                if 'problem_pattern' not in columns:
                    click.echo("   > Tabela solution_templates existe mas com estrutura incorreta. Recriando...")
                    cursor.execute("DROP TABLE solution_templates")
                    table_exists = None
            
            if not table_exists:
                cursor.execute("""
                    CREATE TABLE solution_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem_pattern TEXT NOT NULL UNIQUE,
                        solution_template TEXT NOT NULL,
                        category TEXT NOT NULL,
                        confidence INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    );
                """)
                click.echo("   > Tabela solution_templates criada com sucesso.")

        if current_version < 12:
            click.echo("Atualizando esquema v12 (adicionando 'category' a incidentes)...")
            try:
                cursor.execute("ALTER TABLE open_incidents ADD COLUMN category TEXT;")
            except sqlite3.OperationalError: pass

        # Versão 13: Verificação de integridade das tabelas críticas
        if current_version < 13:
            click.echo("Atualizando esquema v13 (verificação de integridade)...")
            
            # Verifica solution_templates novamente
            cursor.execute("PRAGMA table_info(solution_templates)")
            columns = {row['name'] for row in cursor.fetchall()}
            required_columns = {'id', 'problem_pattern', 'solution_template', 'category', 'confidence', 'created_at'}
            
            if not required_columns.issubset(columns):
                click.echo("   > Recriando tabela solution_templates com estrutura correta...")
                cursor.execute("DROP TABLE IF EXISTS solution_templates")
                cursor.execute("""
                    CREATE TABLE solution_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        problem_pattern TEXT NOT NULL UNIQUE,
                        solution_template TEXT NOT NULL,
                        category TEXT NOT NULL,
                        confidence INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    );
                """)

        if current_version < 14:
            click.echo("Atualizando esquema v14 (Gênese V8: Suporte a Aprendizado Flexível)...")
            try:
                # Adiciona coluna para o tipo de template (HARDCODED vs FLEXIBLE)
                cursor.execute("ALTER TABLE solution_templates ADD COLUMN type TEXT DEFAULT 'HARDCODED';")
                # Adiciona coluna para armazenar o padrão de diff (JSON ou texto formatado)
                cursor.execute("ALTER TABLE solution_templates ADD COLUMN diff_pattern TEXT;")
            except sqlite3.OperationalError:
                pass # Colunas já existem

        if current_version < 15:
            click.echo("Atualizando esquema v15 (Protocolo Chronos: Histórico Robusto)...")
            
            # Tabela de Histórico de Comandos (Ações do Usuário)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_uuid TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    command_name TEXT NOT NULL,
                    full_command_line TEXT NOT NULL,
                    working_dir TEXT NOT NULL,
                    exit_code INTEGER,
                    duration_ms REAL
                );
            """)

            # Tabela de Auditoria de Arquivos (Mutações)
            # Registra o "Antes" e "Depois" de qualquer arquivo tocado pelo Doxoade
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    operation_type TEXT NOT NULL, -- 'MODIFY', 'CREATE', 'DELETE'
                    diff_content TEXT, -- O patch do que mudou
                    backup_path TEXT,
                    FOREIGN KEY (command_id) REFERENCES command_history (id)
                );
            """)
            
            # Índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_hist_ts ON command_history(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_audit_path ON file_audit(file_path);")

        cursor.execute("UPDATE schema_version SET version = ?;", (DB_VERSION,))
        conn.commit()
        click.echo(f"Esquema do banco de dados atualizado com sucesso para a v{DB_VERSION}.")

    finally:
        conn.close()