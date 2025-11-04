# tests/test_doctor_command.py
import os
import sys
import click
import subprocess
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
    
def test_doctor_installs_missing_dependencies(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade doctor' instala dependências ausentes do requirements.txt.
    """
    # FLUXO 1: Preparar um Projeto "Doente"
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    (project_dir / "requirements.txt").write_text("toml", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    venv_python = project_dir / "venv" / "Scripts" / "python.exe" if sys.platform == "win32" else project_dir / "venv" / "bin" / "python"

    # --- CORREÇÃO: Mocking da Confirmação do Usuário ---
    # Substituímos a função de confirmação por uma que sempre retorna True.
    monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: True)

    # FLUXO 2: Executar o Comando 'doctor'
    result = runner.invoke(cli, ['doctor', '.'], catch_exceptions=False)

    # FLUXO 3: Validar o Reparo
    assert result.exit_code == 0, f"O comando doctor falhou. Saída: {result.output}"
    assert "Dependências sincronizadas com sucesso!" in result.output

    check_install_result = subprocess.run(
        [str(venv_python), "-m", "pip", "show", "toml"],
        capture_output=True, text=True
    )
    assert check_install_result.returncode == 0, "O pacote 'toml' não foi encontrado no venv após o reparo."