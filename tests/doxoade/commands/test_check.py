# -*- coding: utf-8 -*-
import pytest
import os
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
from doxoade.commands.check import (
    run_check_logic, 
    _resolve_input_targets, 
    _handle_cache_logic
)

# --- FIXTURES NATIIVAS (Sem dependência de pytest-mock) ---

@pytest.fixture
def mock_dnm():
    """Mock do Directory Navigation Module com caminhos genéricos."""
    with patch('doxoade.commands.check.DNM') as mock:
        instance = mock.return_value
        # Usamos caminhos relativos no mock para evitar conflito de abspath no Windows/Linux
        instance.scan.return_value = ['file1.py', 'file2.py']
        instance.is_ignored.return_value = False
        yield instance

# --- TESTES DE FUNCIONALIDADE ---

def test_resolve_input_targets_file(mock_dnm):
    """Garante que se o input for um arquivo, ele seja priorizado."""
    with patch('os.path.isfile', return_value=True), \
         patch('os.path.abspath', return_value='/root/script.py'):
        targets = _resolve_input_targets('script.py', None, mock_dnm)
        assert len(targets) == 1
        assert targets[0].endswith('script.py')

def test_resolve_input_targets_directory(mock_dnm):
    """Garante que se o input for pasta, o DNM faça o scan e filtre corretamente."""
    # Simulamos que estamos na raiz '/'
    with patch('os.path.isfile', return_value=False), \
         patch('os.path.abspath', side_effect=lambda p: f"/{p.strip('.').strip('/')}".rstrip('/')):
        
        # Agora o scan retorna caminhos que começam com o abspath do input
        mock_dnm.scan.return_value = ['/file1.py', '/file2.py']
        
        targets = _resolve_input_targets('.', None, mock_dnm)
        assert len(targets) == 2

def test_handle_cache_logic_miss(tmp_path):
    """Testa comportamento quando o cache está vazio ou inválido."""
    project_root = str(tmp_path)
    f1 = tmp_path / "new.py"
    f1.write_text("print('hello')", encoding='utf-8')
    
    cache = {}
    files = [str(f1)]
    
    findings, files_to_scan = _handle_cache_logic(files, cache, False, project_root)
    
    assert findings == []
    assert len(files_to_scan) == 1

def test_handle_cache_logic_hit(tmp_path):
    """Testa recuperação de resultados do cache (Performance)."""
    project_root = str(tmp_path)
    f1 = tmp_path / "cached.py"
    f1.write_text("code", encoding='utf-8')
    st = os.stat(f1)
    
    rel_path = "cached.py"
    cache = {
        rel_path: {
            'mtime': st.st_mtime,
            'size': st.st_size,
            'findings': [{'severity': 'INFO', 'message': 'Cached Result'}]
        }
    }
    
    # Precisamos garantir que o rel_path gerado no teste seja igual ao do cache
    with patch('os.path.relpath', return_value=rel_path):
        findings, files_to_scan = _handle_cache_logic([str(f1)], cache, False, project_root)
        
        assert len(findings) == 1
        assert findings[0]['message'] == 'Cached Result'
        assert files_to_scan == []

def test_run_check_logic_contract_check(mock_dnm):
    """
    Verifica se o comando retorna o dicionário correto (Proteção AttributeError).
    Usa patches manuais para evitar a fixture 'mocker'.
    """
    # Mocks de suporte
    with patch('doxoade.commands.check._find_project_root', return_value='.'), \
         patch('doxoade.commands.check._get_venv_python_executable', return_value='python'), \
         patch('doxoade.commands.check._handle_cache_logic', return_value=([], [])), \
         patch('doxoade.commands.check._enrich_findings_with_solutions'), \
         patch('doxoade.commands.check._enrich_with_dependency_analysis'), \
         patch('doxoade.commands.check._update_open_incidents'), \
         patch('doxoade.commands.check.ExecutionLogger') as mock_logger_cls:
        
        # Configura o Logger mockado
        mock_logger = mock_logger_cls.return_value
        mock_logger.__enter__.return_value = mock_logger
        mock_logger.summary = {'errors': 5}
        mock_logger.findings = []
        
        # Executa
        result = run_check_logic('.', fix=False, fast=True, no_cache=True, clones=False, continue_on_error=False)
        
        # Valida o dicionário de retorno (O contrato Gold)
        assert result['summary']['errors'] == 5
        assert isinstance(result['findings'], list)

def test_run_check_logic_no_files(mock_dnm):
    """Garante retorno vazio elegante se não houver arquivos .py."""
    mock_dnm.scan.return_value = []
    with patch('os.path.isfile', return_value=False), \
         patch('doxoade.commands.check._find_project_root', return_value='.'):
        result = run_check_logic('.', False, False, True, False, False)
        assert result['summary']['errors'] == 0
        assert result['findings'] == []