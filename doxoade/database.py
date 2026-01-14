# -*- coding: utf-8 -*-
"""
Módulo de Persistência (Sapiens/Chronos) - v71.1.
Gerencia o ciclo de vida do banco de dados e migrações de esquema.
ESTRATÉGIA: Migration Dispatcher para conformidade MPoT-4/17.
"""

import sqlite3
from pathlib import Path
import click

DB_FILE = Path.home() / '.doxoade' / 'doxoade.db'
DB_VERSION = 18  # Incremento para MaxTelemetry v2

def get_db_connection():
    """Mantida Original: Abre conexão persistente com Row Factory."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- ESPECIALISTAS EM MIGRAÇÃO (MPoT-4: Funções < 60 linhas) ---

def _m_v1_v3_core(cursor):
    """Esquema Inicial: Events, Findings e Solutions."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, doxoade_version TEXT,
        command TEXT NOT NULL, project_path TEXT NOT NULL, execution_time_ms REAL, status TEXT
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, severity TEXT NOT NULL,
        message TEXT NOT NULL, details TEXT, file TEXT, line INTEGER, finding_hash TEXT,
        category TEXT, FOREIGN KEY (event_id) REFERENCES events (id)
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS solutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, finding_hash TEXT NOT NULL UNIQUE,
        stable_content TEXT NOT NULL, commit_hash TEXT NOT NULL, project_path TEXT NOT NULL,
        timestamp TEXT NOT NULL, file_path TEXT NOT NULL, message TEXT, error_line INTEGER
    );""")

def _m_v4_v9_incidents(cursor):
    """Dívida Técnica: Tabela de Incidentes Abertos."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS open_incidents (
        finding_hash TEXT PRIMARY KEY, file_path TEXT NOT NULL,
        commit_hash TEXT NOT NULL, timestamp TEXT NOT NULL,
        project_path TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '',
        line INTEGER, category TEXT
    );""")

def _m_v10_v14_genesis(cursor):
    """Projeto Gênese: IA Simbólica e Templates."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS solution_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_pattern TEXT NOT NULL UNIQUE,
        solution_template TEXT NOT NULL,
        category TEXT NOT NULL,
        confidence INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        type TEXT DEFAULT 'HARDCODED',
        diff_pattern TEXT
    );""")

def _m_v15_chronos(cursor):
    """Protocolo Chronos: Auditoria de Comandos e Arquivos."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS command_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_uuid TEXT NOT NULL,
        timestamp TEXT NOT NULL, command_name TEXT NOT NULL,
        full_command_line TEXT NOT NULL, working_dir TEXT NOT NULL,
        exit_code INTEGER, duration_ms REAL, cpu_percent REAL DEFAULT 0,
        peak_memory_mb REAL DEFAULT 0, io_read_mb REAL DEFAULT 0,
        io_write_mb REAL DEFAULT 0, profile_data TEXT, system_info TEXT,
        line_profile_data TEXT
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, command_id INTEGER NOT NULL,
        file_path TEXT NOT NULL, operation_type TEXT NOT NULL,
        diff_content TEXT, backup_path TEXT,
        FOREIGN KEY (command_id) REFERENCES command_history (id)
    );""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_hist_ts ON command_history(timestamp);")

def _apply_incremental_patches(cursor, current_version):
    """Aplica alterações de colunas em tabelas existentes (Resiliência)."""
    # Exemplo: v6 (Solutions), v7 (Incidents), etc.
    alterations = [
        (2, "ALTER TABLE findings ADD COLUMN category TEXT;"),
        (6, "ALTER TABLE solutions ADD COLUMN message TEXT NOT NULL DEFAULT '';"),
        (12, "ALTER TABLE open_incidents ADD COLUMN category TEXT;")
    ]
    for ver, sql in alterations:
        if current_version < ver:
            try: cursor.execute(sql)
            except sqlite3.OperationalError: pass

# --- ORQUESTRADOR (COMPLEXIDADE REDUZIDA) ---

def init_db():
    """Inicia o banco e despacha migrações de forma granular."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);")
        cursor.execute("SELECT version FROM schema_version UNION SELECT 0 ORDER BY version DESC LIMIT 1;")
        current_version = cursor.fetchone()[0]

        if current_version >= DB_VERSION:
            return

        click.echo(f"🔧 Atualizando Doxoade-DB de v{current_version} para v{DB_VERSION}...")

        # 1. Criação/Migração de Tabelas (Estrutural)
        if current_version < 3: _m_v1_v3_core(cursor)
        if current_version < 9: _m_v4_v9_incidents(cursor)
        if current_version < 14: _m_v10_v14_genesis(cursor)
        if current_version < 18: _m_v15_chronos(cursor)

        # 2. Patches Granulares (Colunas e Índices)
        _apply_incremental_patches(cursor, current_version)

        # 3. Finalização
        cursor.execute("DELETE FROM schema_version;")
        cursor.execute("INSERT INTO schema_version (version) VALUES (?);", (DB_VERSION,))
        conn.commit()
        click.echo(f"✅ Banco de dados sincronizado (Versão {DB_VERSION}).")

    finally:
        conn.close()