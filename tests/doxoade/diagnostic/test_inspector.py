# tests/doxoade/diagnostic/test_inspector.py
import pytest
from doxoade.diagnostic.inspector import SystemInspector

def test_inspector_environment():
    inspector = SystemInspector()
    env = inspector.check_environment()
    
    assert "python_version" in env
    assert "os" in env
    # Deve estar rodando em venv durante os testes
    # assert env["venv_active"] is True 

def test_inspector_core_modules():
    inspector = SystemInspector()
    integrity = inspector.verify_core_modules()
    
    # Verifica se o core está OK
    assert integrity["doxoade.tools.git"] == "OK"
    assert integrity["doxoade.database"] == "OK"

def test_full_diagnosis():
    inspector = SystemInspector()
    report = inspector.run_full_diagnosis()
    assert "git" in report
    assert "integrity" in report