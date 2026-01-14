# -*- coding: utf-8 -*-
import pytest
import sqlite3
import os
from unittest.mock import patch, MagicMock
from doxoade.database import init_db, DB_VERSION

# --- FIXTURES ---

@pytest.fixture
def mock_db_path(tmp_path):
    """Cria um caminho temporário para o banco de dados de teste."""
    db_file = tmp_path / "test_doxoade.db"
    with patch('doxoade.database.DB_FILE', db_file):
        yield db_file

# --- TESTES DE INTEGRIDADE ---

def test_init_db_creates_all_tables(mock_db_path):
    """Verifica se o Migration Dispatcher cria todas as tabelas essenciais."""
    init_db()
    
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()
    
    # Lista de tabelas obrigatórias no v18
    expected_tables = {
        'schema_version', 'events', 'findings', 'solutions', 
        'open_incidents', 'solution_templates', 'command_history', 'file_audit'
    }
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    
    for table in expected_tables:
        assert table in tables, f"Tabela crítica ausente: {table}"
    
    conn.close()

def test_schema_version_is_updated(mock_db_path):
    """Garante que a versão do esquema no banco bate com a constante do código."""
    init_db()
    
    conn = sqlite3.connect(mock_db_path)
    conn.row_factory = sqlite3.Row
    version = conn.execute("SELECT version FROM schema_version").fetchone()['version']
    
    assert version == DB_VERSION
    conn.close()

def test_incremental_patches_resilience(mock_db_path):
    """
    Testa se o sistema é resiliente a migrações repetidas 
    (Simula o erro de coluna duplicada).
    """
    init_db() # Primeira execução (Cria v18)
    
    # Tenta rodar novamente. Não deve crashar.
    try:
        init_db()
    except sqlite3.OperationalError as e:
        pytest.fail(f"init_db falhou em execução subsequente: {e}")

def test_m_v15_chronos_columns(mock_db_path):
    """Verifica se as colunas de telemetria do Chronos (v15/v16) foram criadas."""
    init_db()
    
    conn = sqlite3.connect(mock_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(command_history)")
    columns = {row['name'] for row in cursor.fetchall()}
    
    # Colunas adicionadas na v16
    assert 'cpu_percent' in columns
    assert 'peak_memory_mb' in columns
    assert 'line_profile_data' in columns # v18
    
    conn.close()