# -*- coding: utf-8 -*-
import pytest
from doxoade.commands.webcheck import (
    _validate_html_content, 
    _validate_css_content, 
    _analyze_py_web_content
)

def test_html_validation_native_parser():
    """Garante que o parser nativo detecta problemas de acessibilidade."""
    bad_html = '<img src="test.jpg">' # Sem alt
    findings = _validate_html_content(bad_html, "test.html")
    assert any("alt" in f['message'] for f in findings)
    assert any(f['type'] == 'warning' for f in findings)

def test_css_validation_important_abuse():
    """Garante que o abuso de !important é detectado."""
    heavy_css = "body { color: red !important; background: blue !important; " \
                "display: block !important; border: 1px !important; " \
                "margin: 0 !important; padding: 0 !important; }"
    findings = _validate_css_content(heavy_css, "test.css")
    assert any("excessivo" in f['message'] for f in findings)

def test_nicegui_ast_extraction():
    """Garante que extraímos CSS/HTML de strings Python via AST."""
    # Usando um erro que gera 'Property value expected' no cssutils
    py_code = """
from nicegui import ui
ui.label('Test').style('color: ; background: ::::') 
ui.html('<div>Unclosed div', sanitize=True)
    """
    with open("temp_test.py", "w", encoding="utf-8") as f:
        f.write(py_code)

    findings = _analyze_py_web_content("temp_test.py")
    
    # Agora deve conter mensagens vindo do logger interceptado
    assert any("CSS" in f['message'] for f in findings), "Deveria ter detectado erro de sintaxe CSS no .style()"
    
    import os
    os.remove("temp_test.py")

def test_nicegui_security_sanitize_missing():
    """Garante que o check de segurança do NiceGUI detecta falta de sanitize."""
    py_code = "ui.html('<b>Test</b>')" # Sem o argumento sanitize
    with open("temp_sec.py", "w", encoding="utf-8") as f:
        f.write(py_code)
        
    findings = _analyze_py_web_content("temp_sec.py")
    assert any("sanitize" in f['message'] for f in findings)
    
    import os
    os.remove("temp_sec.py")