# doxoade/database.py
import sqlite3
from pathlib import Path
import click

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 9 # A versão final que precisamos

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
            except sqlite3.OperationalError: pass # Ignora se já existir

        if current_version < 8:
            click.echo("Atualizando esquema v8 (de diff para stable_content)...")
            try:
                # Renomeia a coluna e adiciona a nova coluna para a linha do erro
                cursor.execute("ALTER TABLE solutions RENAME COLUMN resolution_diff TO stable_content;")
                cursor.execute("ALTER TABLE solutions ADD COLUMN error_line INTEGER;")
            except sqlite3.OperationalError:
                # Fallback se a tabela já foi modificada ou não existe
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

        cursor.execute("UPDATE schema_version SET version = ?;", (DB_VERSION,))
        conn.commit()
        click.echo(f"Esquema do banco de dados atualizado com sucesso para a v{DB_VERSION}.")

    finally:
        conn.close()