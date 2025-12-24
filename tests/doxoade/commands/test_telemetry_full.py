# tests/doxoade/commands/test_telemetry_full.py
import sqlite3
import pytest
import json
from click.testing import CliRunner
from doxoade.commands.telemetry import telemetry
from doxoade.database import get_db_connection

@pytest.fixture
def mock_db(monkeypatch, tmp_path):
    """Cria um DB temporário para o teste."""
    db_file = tmp_path / "test_doxoade.db"
    
    def mock_get_conn():
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    monkeypatch.setattr("doxoade.commands.telemetry.get_db_connection", mock_get_conn)
    
    # Inicializa tabela
    conn = mock_get_conn()
    conn.execute("""
        CREATE TABLE command_history (
            id INTEGER PRIMARY KEY,
            session_uuid TEXT, timestamp TEXT, command_name TEXT, 
            full_command_line TEXT, working_dir TEXT, exit_code INTEGER, duration_ms REAL,
            cpu_percent REAL, peak_memory_mb REAL, io_read_mb REAL, io_write_mb REAL, 
            profile_data TEXT, system_info TEXT, line_profile_data TEXT
        )
    """)
    
    # Insere dados de teste
    # Caso 1: Dados Completos
    conn.execute("""
        INSERT INTO command_history (command_name, timestamp, duration_ms, cpu_percent, peak_memory_mb, exit_code)
        VALUES ('CHECK', '2025-01-01T12:00:00', 5000, 45.5, 120.0, 0)
    """)
    
    # Caso 2: Dados Nulos (Teste de Robustez)
    conn.execute("""
        INSERT INTO command_history (command_name, timestamp, duration_ms, cpu_percent, peak_memory_mb, exit_code)
        VALUES ('run', '2025-01-01T12:01:00', NULL, NULL, NULL, 1)
    """)
    
    conn.commit()
    return db_file

def test_telemetry_basic(mock_db):
    runner = CliRunner()
    result = runner.invoke(telemetry, ['-n', '10'])
    assert result.exit_code == 0
    assert "CHECK" in result.output
    assert "RUN" in result.output 
    assert "45.5%" in result.output

def test_telemetry_stats(mock_db):
    runner = CliRunner()
    result = runner.invoke(telemetry, ['--stats'])
    assert result.exit_code == 0
    assert "MÉTRICAS DE PERFORMANCE" in result.output
    assert "CHECK" in result.output

def test_telemetry_case_insensitive_filter(mock_db):
    runner = CliRunner()
    # Busca 'check' minúsculo, deve achar 'CHECK' maiúsculo
    result = runner.invoke(telemetry, ['-c', 'check'])
    assert result.exit_code == 0
    assert "CHECK" in result.output
    assert "run" not in result.output # Não deve mostrar o outro

def test_telemetry_verbose_null_safe(mock_db):
    """Testa se o modo verbose crasha com dados nulos."""
    runner = CliRunner()
    result = runner.invoke(telemetry, ['-v'])
    assert result.exit_code == 0
    # Deve mostrar o registro do 'run' que tem nulls, formatado como 0
    assert "(0ms)" in result.output