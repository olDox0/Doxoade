import toml
import sys
import subprocess
import os
from unittest.mock import MagicMock
from doxoade.shared_tools import _run_git_command

# Garante que o pacote 'doxoade' seja importável a partir do diretório de testes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.shared_tools import _get_project_config, ExecutionLogger

def test_get_project_config_reads_toml(tmp_path, monkeypatch):
    """
    Valida se _get_project_config lê e interpreta o pyproject.toml corretamente.
    """
    # FLUXO 1: Preparar o Ambiente Falso
    project_dir = tmp_path
    
    # Usamos monkeypatch para simular que estamos no diretório do projeto
    monkeypatch.chdir(project_dir)

    config_data = {
        'tool': {
            'doxoade': {
                'source_dir': 'src',
                'ignore': ['docs/', 'data/']
            }
        }
    }
    
    (project_dir / "src").mkdir()
    with open(project_dir / "pyproject.toml", "w", encoding="utf-8") as f:
        toml.dump(config_data, f)
    
    mock_logger = MagicMock(spec=ExecutionLogger)

    # FLUXO 2: Executar a Função Alvo
    config = _get_project_config(mock_logger)

    # FLUXO 3: Validar os Resultados
    assert config['source_dir'] == 'src'
    assert 'docs/' in config['ignore']
    assert 'data/' in config['ignore']
    assert config['search_path_valid'] is True
    # Comparamos os caminhos normalizados para evitar problemas entre Windows e Linux
    assert os.path.normpath(config['search_path']) == os.path.normpath(project_dir / "src")
    mock_logger.add_finding.assert_not_called()

def test_get_project_config_handles_invalid_source_dir(tmp_path, monkeypatch):
    """
    Valida se _get_project_config detecta um 'source_dir' inválido.
    """
    # FLUXO 1: Preparar o Ambiente Falso
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    config_data = {
        'tool': {
            'doxoade': {
                'source_dir': 'non_existent_src'
            }
        }
    }
    with open(project_dir / "pyproject.toml", "w", encoding="utf-8") as f:
        toml.dump(config_data, f)
    
    mock_logger = MagicMock(spec=ExecutionLogger)

    # FLUXO 2: Executar a Função Alvo
    config = _get_project_config(mock_logger)

    # FLUXO 3: Validar os Resultados
    assert config['search_path_valid'] is False
    # Valida se o logger foi chamado com o nível de severidade e a mensagem corretos
    mock_logger.add_finding.assert_called_once_with(
        'CRITICAL',
        f"O diretório de código-fonte '{os.path.normpath(project_dir / 'non_existent_src')}' não existe.",
        details="Verifique a diretiva 'source_dir' no seu pyproject.toml."
    )
    
def test_execution_logger_counts_severity():
    """
    Valida se o ExecutionLogger conta corretamente as severidades dos findings.
    """
    # FLUXO 1: Preparar o Logger
    # Nenhum path ou argumento real é necessário para este teste unitário
    logger = ExecutionLogger("test-command", ".", {})

    # FLUXO 2: Adicionar Múltiplos Findings
    logger.add_finding("CRITICAL", "Mensagem crítica")
    logger.add_finding("ERROR", "Mensagem de erro 1")
    logger.add_finding("ERROR", "Mensagem de erro 2")
    logger.add_finding("WARNING", "Mensagem de aviso 1")
    logger.add_finding("WARNING", "Mensagem de aviso 2")
    logger.add_finding("WARNING", "Mensagem de aviso 3")
    logger.add_finding("INFO", "Mensagem informativa")

    # FLUXO 3: Validar o Sumário
    summary = logger.results['summary']
    assert summary['critical'] == 1
    assert summary['errors'] == 2
    assert summary['warnings'] == 3
    assert summary['info'] == 1

def test_run_git_command_success(monkeypatch):
    """
    Valida se _run_git_command retorna True em uma execução bem-sucedida.
    """
    # FLUXO 1: Preparar o Mock
    # Criamos um objeto que se parece com o resultado de subprocess.run
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Success"
    
    # Usamos monkeypatch para substituir a função real pela nossa simulação
    mock_run = MagicMock(return_value=mock_result)
    monkeypatch.setattr(subprocess, "run", mock_run)

    # FLUXO 2: Executar a Função Alvo
    result = _run_git_command(['status'])

    # FLUXO 3: Validar os Resultados
    assert result is True
    # Verifica se subprocess.run foi chamado com os argumentos corretos
    mock_run.assert_called_once_with(
        ['git', 'status'], capture_output=False, text=True, check=True,
        encoding='utf-8', errors='replace'
    )

def test_run_git_command_failure(monkeypatch):
    """
    Valida se _run_git_command retorna None quando o subprocesso falha.
    """
    # FLUXO 1: Preparar o Mock para simular uma falha
    # O mock é configurado para levantar um erro quando for chamado
    mock_run = MagicMock(side_effect=subprocess.CalledProcessError(1, "cmd"))
    monkeypatch.setattr(subprocess, "run", mock_run)

    # FLUXO 2: Executar a Função Alvo
    result = _run_git_command(['status'])

    # FLUXO 3: Validar os Resultados
    assert result is None
    mock_run.assert_called_once()