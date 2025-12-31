from unittest.mock import patch, MagicMock
import os
#import json

from doxoade.commands.doctor import _check_and_create_venv, _verify_environment
#_prepare_verification_data, _run_verification_probe

# --- Testes para _check_and_create_venv ---

@patch('subprocess.run')
@patch('click.confirm')
@patch('os.path.isdir')
def test_check_and_create_venv_when_missing(mock_isdir, mock_confirm, mock_subprocess_run):
    mock_isdir.return_value = False
    mock_confirm.return_value = True
    mock_subprocess_run.return_value = MagicMock()
    mock_logger = MagicMock()
    result = _check_and_create_venv('.', mock_logger)
    assert result is True
    expected_path = os.path.join('.', 'venv')
    mock_isdir.assert_called_once_with(expected_path)
    mock_confirm.assert_called_once()
    mock_subprocess_run.assert_called_once()

@patch('os.path.isdir')
def test_check_and_create_venv_when_exists(mock_isdir):
    mock_isdir.return_value = True
    mock_logger = MagicMock()
    result = _check_and_create_venv('.', mock_logger)
    assert result is True
    expected_path = os.path.join('.', 'venv')
    mock_isdir.assert_called_once_with(expected_path)

# --- Testes para _verify_environment ---

@patch('doxoade.commands.doctor._run_verification_probe')
@patch('doxoade.commands.doctor._prepare_verification_data')
def test_verify_environment_dependencies_ok(mock_prepare_data, mock_run_probe):
    """Testa o orquestrador _verify_environment no cenário feliz."""
    mock_logger = MagicMock()
    
    # Simula as funções auxiliares
    mock_prepare_data.return_value = ({"requests", "click"}, None)
    mock_run_probe.return_value = {'status': 'ok', 'message': 'Dependências OK e ambiente isolado.'}
    
    result = _verify_environment('.', mock_logger)
    
    # A verificação crucial: esperamos a mensagem exata que a sonda retorna.
    assert result.get('status') == 'ok'
    assert result.get('message') == 'Dependências OK e ambiente isolado.'

@patch('doxoade.commands.doctor._run_verification_probe')
@patch('doxoade.commands.doctor._prepare_verification_data')
def test_verify_environment_dependency_missing(mock_prepare_data, mock_run_probe):
    """Testa o orquestrador _verify_environment no cenário de falha."""
    mock_logger = MagicMock()

    mock_prepare_data.return_value = ({"requests", "click"}, None)
    mock_run_probe.return_value = {'status': 'error', 'message': 'Pacotes não encontrados: requests'}
    
    result = _verify_environment('.', mock_logger)
    
    assert result.get('status') == 'error'
    assert 'Pacotes não encontrados: requests' in result.get('message', '')