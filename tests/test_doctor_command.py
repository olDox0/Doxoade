# tests/test_doctor_command.py
import os
import sys
from click.testing import CliRunner

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.doxoade import cli

def test_doctor_creates_venv_if_missing(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade doctor' detecta um venv ausente, oferece para criar e o cria.
    """
    # FLUXO 1: Preparar o Projeto "Quebrado" (sem venv)
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    
    (project_dir / "requirements.txt").touch()

    # FLUXO 2: Executar o Comando Alvo, simulando a entrada 'y'
    result = runner.invoke(cli, ['doctor', '.'], input='y\n', catch_exceptions=False)

    # FLUXO 3: Validar os Efeitos Colaterais
    assert result.exit_code == 0, f"O comando doctor falhou. Saída: {result.output}"
    
    # Verifica se a pasta venv foi realmente criada
    assert (project_dir / "venv").is_dir(), "O doctor falhou em criar o diretório venv."
    
    # Verifica se a saída de texto contém a confirmação de sucesso
    assert "Ambiente virtual 'venv' criado com sucesso!" in result.output