# tests/test_rebuild_command.py
import os
import sys
import subprocess
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from doxoade.commands.rebuild import _install_requirements

def test_install_requirements_succeeds_cleanly(tmp_path, monkeypatch):
    """
    Valida se _install_requirements passa em um cenário limpo.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    (project_dir / "requirements.txt").write_text("toml==0.10.2", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True, capture_output=True)
    
    mock_logger = MagicMock()
    result = _install_requirements(str(project_dir), mock_logger)
    
    assert result is True
    mock_logger.add_finding.assert_any_call('info', "Verificação 'pip check' bem-sucedida.")

def test_install_requirements_fails_on_conflict(tmp_path, monkeypatch):
    """
    Valida se _install_requirements falha com um requirements.txt conflitante.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    
    # Requisito Contraditório que o `pip` não pode resolver.
    conflicting_reqs = "toml==0.10.0\\ntoml==0.10.2"
    (project_dir / "requirements.txt").write_text(conflicting_reqs, encoding="utf-8")
    
    subprocess.run([sys.executable, "-m", "venv", "venv"], check=True, capture_output=True)
    
    mock_logger = MagicMock()
    
    result = _install_requirements(str(project_dir), mock_logger)

    assert result is False
    error_call = mock_logger.add_finding.call_args_list[0]
    assert error_call.args[0] == 'error'
    assert "Falha ao instalar dependências via pip" in error_call.args[1]
    
    # CORREÇÃO: Valida a mensagem de erro correta do pip moderno.
    assert "No matching distribution found for" in error_call.kwargs['details']