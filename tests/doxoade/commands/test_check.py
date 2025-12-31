# -*- coding: utf-8 -*-
"""
Suíte de Testes de Regressão: Comando Check.
Valida a orquestração de sondas, integridade do cache e lógica de templates.
"""

import pytest
import json
import os
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from doxoade.commands.check import (
    _load_cache, 
    _save_cache, 
    _run_syntax_check, 
    _match_finding_to_template,
    _run_pyflakes_check
)

def test_load_cache_fallback(tmp_path):
    """Garante que o cache retorna dicionário vazio se o arquivo não existir."""
    with patch('doxoade.commands.check.CHECK_CACHE_FILE', tmp_path / "fake_cache.json"):
        cache = _load_cache()
        assert isinstance(cache, dict)
        assert len(cache) == 0

def test_save_cache_persistence(tmp_path):
    """Verifica se o sistema cria o diretório e salva o JSON corretamente."""
    cache_dir = tmp_path / ".doxoade_cache"
    cache_file = cache_dir / "check_cache.json"
    
    with patch('doxoade.commands.check.CACHE_DIR', cache_dir), \
         patch('doxoade.commands.check.CHECK_CACHE_FILE', cache_file):
        
        test_data = {"file.py": {"hash": "123"}}
        _save_cache(test_data)
        
        assert cache_file.exists()
        with open(cache_file, 'r') as f:
            saved = json.load(f)
            assert saved["file.py"]["hash"] == "123"

@patch('doxoade.commands.check._run_probe')
def test_run_syntax_check_detects_error(mock_probe):
    """Garante que erros de sintaxe capturados via stderr são parseados."""
    # Simula falha catastrófica de sintaxe
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stderr = "File 'main.py', line 10: invalid syntax"
    mock_probe.return_value = mock_res
    
    findings = _run_syntax_check("main.py", "python")
    
    assert len(findings) == 1
    assert findings[0]['category'] == 'SYNTAX'
    assert findings[0]['line'] == 10
    assert "invalid syntax" in findings[0]['message']

def test_pyflakes_text_parsing():
    """Valida a conversão de strings do Pyflakes para objetos finding do Doxoade."""
    # Simula a saída padrão do pyflakes/sonda estática
    mock_stdout = "main.py:5:1: 'os' imported but unused\nmain.py:12:5: undefined name 'x'"
    
    with patch('doxoade.commands.check._run_probe') as mock_probe:
        mock_res = MagicMock()
        mock_res.stdout = mock_stdout
        mock_probe.return_value = mock_res
        
        findings = _run_pyflakes_check("main.py", "python")
        
        assert len(findings) == 2
        assert findings[0]['category'] == 'DEADCODE'
        assert findings[0]['line'] == 5
        assert findings[1]['category'] == 'RUNTIME-RISK'
        assert findings[1]['line'] == 12

def test_match_finding_to_template_logic():
    """Verifica se o motor Gênese casa erros concretos com templates abstratos."""
    # Mock de um template do banco de dados
    mock_template = MagicMock()
    mock_template.__getitem__.side_effect = {
        'category': 'DEADCODE',
        'problem_pattern': "'<MODULE>' imported but unused",
        'solution_template': 'FIX_UNUSED_IMPORT'
    }.get
    
    finding = {
        'message': "'sys' imported but unused",
        'category': 'DEADCODE'
    }
    
    result = _match_finding_to_template(finding, [mock_template])
    
    assert result['type'] == 'FIX_UNUSED_IMPORT'
    assert result['context']['var_name'] == 'sys'

def test_match_finding_no_match():
    """Garante que o contrato Gold retorna dicionário vazio para erros desconhecidos."""
    finding = {'message': 'Erro desconhecido', 'category': 'UNKNOWN'}
    result = _match_finding_to_template(finding, [])
    
    assert result['type'] is None
    assert result['context'] == {}