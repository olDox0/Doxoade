# tests/test_check_command.py
import sys
from pathlib import Path
from click.testing import CliRunner

# Não precisa mais de sys.path.insert, o pytest lida com isso
from doxoade.cli import cli
from doxoade.commands import check as check_module

# --- FUNÇÃO HELPER ROBUSTA ---
def setup_project(tmp_path, code_content, toml_content=""):
    """Cria um projeto de teste em um diretório temporário."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(code_content, encoding="utf-8")
    if toml_content:
        (project_dir / "pyproject.toml").write_text(toml_content, encoding="utf-8")
    return project_dir

# --- SUÍTE DE TESTES ATUALIZADA ---

def test_check_passes_on_clean_code(runner: CliRunner, tmp_path, monkeypatch):
    """Verifica se o check passa em um código sem erros."""
    project_dir = setup_project(tmp_path, "print('hello world')")
    monkeypatch.chdir(project_dir)
    
    # Mock para evitar a criação real do venv
    monkeypatch.setattr(check_module, '_get_venv_python_executable', lambda: sys.executable)
    
    result = runner.invoke(cli, ['check', '.'], catch_exceptions=False)
    
    assert result.exit_code == 0
    assert "Nenhum problema encontrado" in result.output

def test_check_finds_syntax_error(runner: CliRunner, tmp_path, monkeypatch):
    """Verifica se a sonda de sintaxe captura erros fatais."""
    
    # --- CÓDIGO CORRIGIDO: Agora tem um SyntaxError real ---
    invalid_code = "def my_function() pass"  # Faltando os dois-pontos
    
    project_dir = setup_project(tmp_path, invalid_code)
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(check_module, '_get_venv_python_executable', lambda: sys.executable)

    result = runner.invoke(cli, ['check', '.'], catch_exceptions=True)
    
    # Esta asserção agora vai passar
    assert result.exit_code != 0
    assert "Erro de sintaxe" in result.output
    assert "CRITICAL" in result.output

def test_check_finds_unused_import(runner: CliRunner, tmp_path, monkeypatch):
    """Verifica se a sonda estática (pyflakes) captura imports não utilizados."""
    project_dir = setup_project(tmp_path, "import os\nprint('hello')")
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(check_module, '_get_venv_python_executable', lambda: sys.executable)

    result = runner.invoke(cli, ['check', '.'], catch_exceptions=False)
    
    assert result.exit_code == 0 # Imports não utilizados são 'ERROR', não fazem o build falhar
    assert "'os' imported but unused" in result.output
    assert "ERROR" in result.output

def test_check_finds_unresolved_import(runner: CliRunner, tmp_path, monkeypatch):
    """Verifica se a sonda de imports captura módulos inexistentes."""
    project_dir = setup_project(tmp_path, "import modulo_que_nao_existe_de_jeito_nenhum")
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(check_module, '_get_venv_python_executable', lambda: sys.executable)

    result = runner.invoke(cli, ['check', '.'], catch_exceptions=False)
    
    assert result.exit_code != 0 # Import não resolvido é 'CRITICAL'
    assert "Import não resolvido" in result.output
    assert "CRITICAL" in result.output

def test_check_flag_no_imports_ignores_unresolved_import(runner: CliRunner, tmp_path, monkeypatch):
    """Verifica se a flag --no-imports desativa a verificação de imports."""
    project_dir = setup_project(tmp_path, "import modulo_que_nao_existe_de_jeito_nenhum")
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(check_module, '_get_venv_python_executable', lambda: sys.executable)

    # Executa com a flag --no-imports
    result = runner.invoke(cli, ['check', '.', '--no-imports'], catch_exceptions=False)
    
    # O comando deve passar, pois o erro crítico de import foi ignorado
    assert result.exit_code == 0
    assert "Import não resolvido" not in result.output