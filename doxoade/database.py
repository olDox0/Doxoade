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
    
    # --- UTILITARIO 1: Gerenciamento de Versão do Esquema ---
    cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);")
    
    cursor.execute("SELECT version FROM schema_version;")
    current_version_row = cursor.fetchone()
    current_version = current_version_row['version'] if current_version_row else 0

    if current_version < DB_VERSION:
        # --- UTILITARIO 2: Criação do Esquema V1 ---
        if current_version < 1:
            # Tabela para registrar cada execução de comando
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
            
            # Tabela para registrar cada finding (erro/aviso) de um evento
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
            
            # Insere a nova versão do esquema
            cursor.execute("INSERT INTO schema_version (version) VALUES (?);", (1,))
        
        # Futuras migrações viriam aqui. Exemplo:
        # if current_version < 2:
        #     cursor.execute("ALTER TABLE events ADD COLUMN git_hash TEXT;")
        #     cursor.execute("UPDATE schema_version SET version = 2;")
            
        conn.commit()
    
    conn.close()