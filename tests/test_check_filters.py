# tests/test_check_filters.py
import pytest
from doxoade.commands.check_filters import filter_and_inject_findings

def test_filter_removes_silenced_error(tmp_path):
    """Testa se # noqa remove o erro."""
    # Setup
    f = tmp_path / "test.py"
    f.write_text("x = 1 # noqa\n", encoding="utf-8")
    
    findings = [{
        'file': str(f),
        'line': 1,
        'message': "Erro de exemplo",
        'severity': "ERROR"
    }]
    
    # Action
    result = filter_and_inject_findings(findings, str(f))
    
    # Assert
    assert len(result) == 0

def test_filter_keeps_normal_error(tmp_path):
    """Testa se erro sem tag é mantido."""
    f = tmp_path / "test.py"
    f.write_text("x = 1\n", encoding="utf-8")
    
    findings = [{
        'file': str(f),
        'line': 1,
        'message': "Erro real",
        'severity': "ERROR"
    }]
    
    result = filter_and_inject_findings(findings, str(f))
    
    assert len(result) == 1
    assert result[0]['message'] == "Erro real"

def test_inject_qa_tags(tmp_path):
    """Testa se # TODO cria um finding."""
    f = tmp_path / "test.py"
    f.write_text("# TODO: Refatorar isso\n", encoding="utf-8")
    
    findings = [] # Sem erros do linter
    
    result = filter_and_inject_findings(findings, str(f))
    
    assert len(result) == 1
    assert result[0]['category'] == 'QA-REMINDER'
    assert "[TODO] Refatorar isso" in result[0]['message']
    assert result[0]['severity'] == 'INFO'