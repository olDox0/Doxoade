# -*- coding: utf-8 -*-
import pytest
import os
from doxoade.commands.check_filters import filter_and_inject_findings

def test_filter_noqa_silencing(tmp_path):
    """Garante que erros em linhas com # noqa sejam removidos."""
    file_p = tmp_path / "app.py"
    file_p.write_text("import sys # noqa", encoding="utf-8")
    
    findings = [{
        'message': "'sys' imported but unused",
        'line': 1,
        'category': 'DEADCODE',
        'severity': 'WARNING'
    }]
    
    # Com # noqa, a lista deve vir vazia
    result = filter_and_inject_findings(findings, str(file_p))
    assert len(result) == 0

def test_facade_file_logic(tmp_path):
    """Verifica se avisos de 'unused' são ignorados em arquivos de fachada."""
    file_p = tmp_path / "shared_tools.py" # Arquivo na whitelist
    file_p.write_text("from os import *", encoding="utf-8")
    
    findings = [{
        'message': "'os' imported but unused",
        'line': 1,
        'category': 'DEADCODE'
    }]
    
    result = filter_and_inject_findings(findings, str(file_p))
    assert len(result) == 0

def test_todo_injection(tmp_path):
    """Valida se comentários TODO viram achados INFO."""
    file_p = tmp_path / "logic.py"
    file_p.write_text("# TODO: implementar core\n# ADTI: bug critico", encoding="utf-8")
    
    result = filter_and_inject_findings([], str(file_p))
    
    assert len(result) == 2
    assert any(f['severity'] == 'INFO' and 'TODO' in f['message'] for f in result)
    assert any(f['severity'] == 'CRITICAL' and 'ADTI' in f['message'] for f in result)