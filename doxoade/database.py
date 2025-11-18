# doxoade/database.py
import sqlite3
from pathlib import Path

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 3 # <-- MUDANÇA 1: A versão do nosso esquema agora é 3

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
        
        # Garante que a tabela de versão tenha pelo menos uma entrada se for nova
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO schema_version (version) VALUES (0);")

        cursor.execute("SELECT version FROM schema_version;")
        current_version_row = cursor.fetchone()
        current_version = current_version_row['version'] if current_version_row else 0

        # --- Lógica de Migração ---
        if current_version < DB_VERSION:
            
            # Migração para a Versão 1 (Criação Inicial)
            if current_version < 1:
                click.echo("Criando o esquema inicial do banco de dados (v1)...") # Adicionado feedback
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    doxoade_version TEXT,
                    command TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    execution_time_ms REAL,
                    status TEXT
                );
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    file TEXT,
                    line INTEGER,
                    finding_hash TEXT,
                    FOREIGN KEY (event_id) REFERENCES events (id)
                );
                """)
            
            # Migração para a Versão 2 (Adiciona Categoria)
            if current_version < 2:
                click.echo("Atualizando o esquema do banco de dados para v2 (adicionando 'category')...") # Adicionado feedback
                try:
                    cursor.execute("ALTER TABLE findings ADD COLUMN category TEXT;")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e): raise e

            # --- INÍCIO DA NOVA LÓGICA DE MIGRAÇÃO ---
            # Migração para a Versão 3 (Tabela de Soluções)
            if current_version < 3:
                click.echo("Atualizando o esquema do banco de dados para v3 (adicionando tabela de soluções)...") # Adicionado feedback
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS solutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    finding_hash TEXT NOT NULL UNIQUE, -- O hash do problema que foi resolvido
                    resolution_diff TEXT NOT NULL,     -- O 'git diff' que corrigiu o problema
                    commit_hash TEXT NOT NULL,         -- O hash do commit da solução
                    project_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    file_path TEXT NOT NULL            -- O arquivo que foi modificado
                );
                """)
            # --- FIM DA NOVA LÓGICA ---

            # Atualiza a versão do esquema para a versão final
            cursor.execute("UPDATE schema_version SET version = ?;", (DB_VERSION,))
            conn.commit()
            click.echo(f"Esquema do banco de dados atualizado para a versão {DB_VERSION}.")

    finally:
        conn.close()

# Adiciona o import de click para o feedback no console
import click