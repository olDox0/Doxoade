# doxoade/database.py
import sqlite3
from pathlib import Path

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 1 # A versão atual do nosso esquema de banco de dados

def get_db_connection():
    """Cria o diretório se necessário e retorna uma conexão com o banco de dados."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False é crucial para futuras aplicações multithread
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
    return conn

def init_db():
    """
    Cria e/ou migra o esquema do banco de dados para a versão mais recente.
    Seguro para ser executado a cada inicialização.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Tabela para gerenciar a versão do esquema
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);")
        
        cursor.execute("SELECT version FROM schema_version;")
        current_version_row = cursor.fetchone()
        current_version = current_version_row['version'] if current_version_row else 0

        # --- Lógica de Migração ---
        if current_version < DB_VERSION:
            
            # Migração para a Versão 1 (Criação Inicial)
            if current_version < 1:
                print("Criando o esquema inicial do banco de dados (v1)...")
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
                cursor.execute("INSERT INTO schema_version (version) VALUES (?);", (1,))
                current_version = 1
                print("Esquema v1 criado com sucesso.")

            # Migração para a Versão 2 (Adiciona Categoria)
            if current_version < 2:
                print("Atualizando o esquema do banco de dados para v2 (adicionando 'category')...")
                try:
                    cursor.execute("ALTER TABLE findings ADD COLUMN category TEXT;")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        raise # Re-levanta o erro se não for o que esperamos
                
                # Independentemente de ter dado erro ou não, atualiza a versão.
                cursor.execute("UPDATE schema_version SET version = ? WHERE version = ?;", (2, 1))
                current_version = 2
                print("Esquema v2 atualizado com sucesso.")

            conn.commit()
    
    finally:
        conn.close()