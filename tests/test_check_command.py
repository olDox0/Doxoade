# tests/test_check_command.py
import os
import sys
import subprocess
from click.testing import CliRunner
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from doxoade.doxoade import cli

def _setup_test_env(project_dir: Path):
    subprocess.run([sys.executable, "-m", "venv", project_dir / "venv"], check=True, capture_output=True)
    venv_python = project_dir / "venv" / "Scripts" / "python.exe" if sys.platform == "win32" else project_dir / "venv" / "bin" / "python"
    subprocess.run([str(venv_python), "-m", "pip", "install", "pyflakes"], check=True, capture_output=True)

def test_check_passes_on_clean_code(runner: CliRunner, tmp_path, monkeypatch):
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    (project_dir / "main.py").write_text("print('hello world')", encoding="utf-8")
    (project_dir / "pyproject.toml").touch()
    _setup_test_env(project_dir)
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Nenhum problema encontrado" in result.output

def test_check_finds_syntax_error(runner: CliRunner, tmp_path, monkeypatch):
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    invalid_code = "def my_function()\n    pass"
    (project_dir / "broken_code.py").write_text(invalid_code, encoding="utf-8")
    (project_dir / "pyproject.toml").touch()
    _setup_test_env(project_dir)
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=True)
    assert result.exit_code != 0
    assert "Erro de sintaxe" in result.output
    assert "CRITICAL" in result.output

def test_check_finds_unused_import(runner: CliRunner, tmp_path, monkeypatch):
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    (project_dir / "main.py").write_text("import os\nimport sys\n\nprint(sys.version)", encoding="utf-8")
    (project_dir / "pyproject.toml").touch()
    _setup_test_env(project_dir)
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=False)
    assert result.exit_code == 0
    assert "'os' imported but unused" in result.output
    assert "ERROR" in result.output

def test_check_finds_unresolved_import(runner: CliRunner, tmp_path, monkeypatch):
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    subprocess.run([sys.executable, "-m", "venv", "venv"], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "main.py").write_text("import pacote_que_nao_existe", encoding="utf-8")
    (project_dir / "pyproject.toml").touch()
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=True)
    assert result.exit_code != 0
    assert "Import não resolvido" in result.output
    assert "pacote_que_nao_existe" in result.output
    assert "CRITICAL" in result.output