# tests/test_init_command.py
import os
import sys
from click.testing import CliRunner

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.doxoade import cli

def test_init_creates_project_structure(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade init' cria a estrutura de diretórios e arquivos esperada.
    """
    # FLUXO 1: Preparar o Ambiente de Teste
    base_dir = tmp_path
    monkeypatch.chdir(base_dir)
    project_name = "meu-projeto-teste"

    # FLUXO 2: Executar o Comando Alvo
    result = runner.invoke(cli, ['init', project_name], catch_exceptions=False)

    # FLUXO 3: Validar os Efeitos Colaterais
    assert result.exit_code == 0, f"O comando init falhou. Saída: {result.output}"
    
    project_path = base_dir / project_name
    assert project_path.is_dir(), "O diretório do projeto não foi criado."
    assert (project_path / ".gitignore").is_file(), "O arquivo .gitignore não foi criado."
    assert (project_path / "requirements.txt").is_file(), "O arquivo requirements.txt não foi criado."
    assert (project_path / "main.py").is_file(), "O arquivo main.py não foi criado."
    assert (project_path / "venv").is_dir(), "O diretório venv não foi criado."
    assert (project_path / ".git").is_dir(), "O repositório Git não foi inicializado."