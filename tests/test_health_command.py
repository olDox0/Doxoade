# tests/test_health_command.py
import os
import sys
import json
import subprocess
from unittest.mock import MagicMock
from doxoade.commands.health import _analyze_test_coverage

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.commands.health import _analyze_complexity

def test_analyze_complexity_logic_directly(tmp_path):
    """
    Valida a lógica de _analyze_complexity diretamente (Teste de Unidade Puro).
    """
    # FLUXO 1: Preparar o Projeto "Doente"
    project_dir = tmp_path
    
    # Este código tem uma complexidade real de 37, como medido pelo radon.
    complex_code = """
def very_complex_function(a, b, c, d, e, f):
    if a: return 1
    elif b: return 2
    elif c: return 3
    elif d: return 4
    if a and b: return 5
    if c and d: return 6
    if a or c: return 7
    if b or d: return 8
    if a and c: return 9
    if b and d: return 10
    if a and d: return 11
    if b and c: return 12
    if e and a: return 13
    if e and b: return 14
    if e and c: return 15
    if e and d: return 16
    if f or a: return 17
    if f or b: return 18
    if f or c: return 19
    if f or d: return 20
    return 0
"""
    complex_file_path = project_dir / "complex_code.py"
    complex_file_path.write_text(complex_code, encoding="utf-8")

    # FLUXO 2: Executar a Função Alvo Diretamente
    # Usamos um threshold de 36 para garantir que a complexidade 37 seja detectada.
    findings = _analyze_complexity([str(complex_file_path)], threshold=36)

    # FLUXO 3: Validar a Saída de Dados
    assert len(findings) == 1
    
    finding = findings[0]
    assert finding['severity'] == 'WARNING'
    # CORREÇÃO FINAL E DEFINITIVA: Usa o valor medido (37).
    assert "Função 'very_complex_function' tem complexidade alta (37)." in finding['message']
    assert finding['line'] == 2
    
def test_analyze_test_coverage_success(tmp_path, monkeypatch):
    """
    Valida o 'caminho feliz' da análise de cobertura de testes.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    
    # Mock para _get_venv_python_executable
    monkeypatch.setattr("doxoade.commands.health._get_venv_python_executable", lambda: sys.executable)
    
    # Mock para subprocess.run
    mock_run = MagicMock()
    # A primeira chamada (pytest) retorna sucesso. A segunda (coverage json) também.
    mock_run.side_effect = [
        MagicMock(returncode=0), 
        MagicMock(returncode=0)
    ]
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Mock para a criação do coverage.json
    coverage_data = {"totals": {"percent_covered": 95.0}}
    (project_dir / "coverage.json").write_text(json.dumps(coverage_data))
    
    findings = _analyze_test_coverage(str(project_dir), min_coverage=90, source_dir='.')
    
    assert findings == []

def test_analyze_test_coverage_low_coverage(tmp_path, monkeypatch):
    """
    Valida a detecção de baixa cobertura de testes.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("doxoade.commands.health._get_venv_python_executable", lambda: sys.executable)
    
    mock_run = MagicMock()
    mock_run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=0)]
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Cenário "doente": cobertura abaixo do limiar
    coverage_data = {"totals": {"percent_covered": 50.0}}
    (project_dir / "coverage.json").write_text(json.dumps(coverage_data))
    
    findings = _analyze_test_coverage(str(project_dir), min_coverage=90, source_dir='.')
    
    assert len(findings) == 1
    assert findings[0]['severity'] == 'WARNING'
    assert "Cobertura de testes está baixa: 50.00%." in findings[0]['message']

def test_analyze_test_coverage_pytest_fails(tmp_path, monkeypatch):
    """
    Valida o tratamento de falha na execução do pytest.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("doxoade.commands.health._get_venv_python_executable", lambda: sys.executable)
    
    # Cenário "doente": a primeira chamada (pytest) retorna um código de erro.
    mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="Test failed", stderr="Error details"))
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    findings = _analyze_test_coverage(str(project_dir), min_coverage=90, source_dir='.')
    
    assert len(findings) == 1
    assert findings[0]['severity'] == 'ERROR'
    assert "A suíte de testes falhou." in findings[0]['message']