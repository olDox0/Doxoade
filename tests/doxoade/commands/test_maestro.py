# -*- coding: utf-8 -*-
import pytest
import os
from unittest.mock import MagicMock, patch
from doxoade.commands.maestro import MaestroInterpreter

# --- FIXTURES ---

@pytest.fixture
def maestro():
    """Instância limpa do intérprete Maestro."""
    return MaestroInterpreter()

# --- TESTES DE LÓGICA E VARIÁVEIS ---

def test_maestro_variable_assignment_and_resolution(maestro):
    """Testa se SET e a resolução de variáveis {{var}} funcionam."""
    maestro.lines = [
        'SET name = "Dox"',
        'SET version = 71'
    ]
    maestro.run()
    
    assert maestro.variables['name'] == "Dox"
    assert maestro.variables['version'] == 71
    
    resolved = maestro._resolve_vars("Ola {name}, v{version}")
    assert resolved == "Ola Dox, v71"

def test_maestro_increment(maestro):
    """Testa o comando INC."""
    maestro.variables['count'] = 10
    maestro._cmd_vars("INC count")
    assert maestro.variables['count'] == 11

def test_maestro_if_logic_true(maestro):
    """Testa se o bloco IF é executado quando a condição é verdadeira."""
    maestro.variables['status'] = "OK"
    maestro.lines = [
        'IF status == "OK"',
        '  SET outcome = "success"',
        'END'
    ]
    maestro.run()
    assert maestro.variables['outcome'] == "success"

def test_maestro_if_logic_false(maestro):
    """Testa se o Maestro pula o bloco IF quando a condição é falsa."""
    maestro.variables['status'] = "ERROR"
    maestro.lines = [
        'IF status == "OK"',
        '  SET outcome = "should_not_run"',
        'END',
        'SET final = "done"'
    ]
    maestro.run()
    assert 'outcome' not in maestro.variables
    assert maestro.variables['final'] == "done"

def test_maestro_for_loop(maestro):
    """Testa iteração com o comando FOR."""
    maestro.variables['items'] = ["a", "b", "c"]
    maestro.lines = [
        'SET log = ""',
        'FOR i IN items',
        '  # Nota: Concatenacao manual via SET para teste',
        '  SET last = "{i}"',
        'END'
    ]
    maestro.run()
    # Ao final do loop, a variável 'last' deve ser o último item
    assert maestro.variables['last'] == "c"

# --- TESTES DE COMANDOS DE SISTEMA (MOCKS) ---

@patch('subprocess.run')
def test_maestro_run_command(mock_sub, maestro):
    """Verifica se o comando RUN chama o subprocesso corretamente (sem shell)."""
    # Configura o retorno do mock
    mock_sub.return_value = MagicMock(stdout="Success Output", stderr="", returncode=0)
    
    maestro.lines = ['RUN echo "hello" -> RESULT']
    maestro.run()
    
    # Verifica se foi chamado com shell=False (Protocolo Aegis)
    args, kwargs = mock_sub.call_args
    assert kwargs['shell'] is False
    assert "echo" in args[0]
    assert maestro.variables['RESULT'] == "Success Output"

def test_maestro_find_line_number(maestro, tmp_path):
    """Testa o utilitário rápido de localização de linha."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("linha1\nALVO_AQUI\nlinha3", encoding='utf-8')
    
    maestro.lines = [f'FIND_LINE_NUMBER "ALVO_AQUI" IN "{test_file}" -> POS']
    maestro.run()
    
    # Índice 1 (segunda linha)
    assert maestro.variables['POS'] == "1"

@patch('click.echo')
def test_maestro_print_colors(mock_echo, maestro):
    """Garante que o despacho de cores no PRINT funciona."""
    maestro._cmd_print('PRINT-RED "Erro Grave"')
    # Verifica se o click.echo foi chamado com a cor vermelha
    args, _ = mock_echo.call_args
    assert "\x1b[31m" in args[0] # Código ANSI para vermelho