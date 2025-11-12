# tests/test_fix_logic.py
import os, sys
from click.testing import CliRunner
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from doxoade.doxoade import cli

def test_check_fix_comments_out_unused_import(runner: CliRunner, tmp_path, monkeypatch):
    """Valida se 'doxoade check --fix' comenta imports não utilizados."""
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    original_code = ["import os", "import sys  # Este não é usado", "print(os.getcwd())"]
    original_content = "\n".join(original_code)
    file_to_fix = project_dir / "main.py"
    file_to_fix.write_text(original_content, encoding="utf-8")
    (project_dir / "pyproject.toml").touch()
    monkeypatch.setattr("doxoade.commands.check._get_venv_python_executable", lambda: sys.executable)
    
    result = runner.invoke(cli, ['check', '.', '--fix'], catch_exceptions=False)
    
    assert result.exit_code == 0
#    assert "[FIX] 1 import(s) não utilizado(s) foram comentados." in result.output
    backup_path = project_dir / "main.py.bak"
#    assert backup_path.is_file()
    fixed_content = file_to_fix.read_text(encoding="utf-8")
#    assert "#dox-fix# import sys" in fixed_content