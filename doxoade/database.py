import sqlite3
from pathlib import Path

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'

def get_db_connection():
    """Cria o diretório se necessário e retorna uma conexão com o banco de dados."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def init_db():
    """
    Cria as tabelas do banco de dados se elas não existirem.
    Seguro para ser executado a cada inicialização.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        details TEXT,
        file TEXT,
        line INTEGER,
        finding_hash TEXT,
        FOREIGN KEY (event_id) REFERENCES events (id)
    );
    """)
    
    # (Reservado para o futuro) Tabela para os insights aprendidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        finding_hash TEXT UNIQUE NOT NULL,
        solution_diff TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    
    conn.commit()
    conn.close()