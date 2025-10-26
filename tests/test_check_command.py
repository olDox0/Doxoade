import os
from click.testing import CliRunner
import sys

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.doxoade import cli

def test_check_finds_syntax_error(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade check' detecta um SyntaxError.
    """
    # FLUXO 1: Preparar o Projeto "Doente"
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    invalid_code = "def my_function()\n    pass"  # ':' faltando
    (project_dir / "broken_code.py").write_text(invalid_code, encoding="utf-8")
    
    # Simula um venv e pyproject.toml para que o check tenha um ambiente válido
    (project_dir / "venv").mkdir()
    (project_dir / "pyproject.toml").touch()

    # FLUXO 2: Executar o Comando Alvo
    # Usamos catch_exceptions=True porque esperamos um sys.exit(1)
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=True)

    # FLUXO 3: Validar o Diagnóstico
    assert result.exit_code != 0, "O comando deveria falhar, mas retornou sucesso."
    assert "Erro de sintaxe impede a análise." in result.output
    # Verifica se a severidade CRITICAL foi atribuída
    assert "CRITICAL" in result.output