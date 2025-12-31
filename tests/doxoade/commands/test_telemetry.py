# -*- coding: utf-8 -*-
"""Teste de regressão para o MaxTelemetry."""
import pytest
import json # <--- FIX: Adicionado import faltante
from unittest.mock import MagicMock, patch
from doxoade.commands.telemetry import _analyze_processing_detailed, _render_resource_bar

def test_telemetry_bar_rendering(capsys):
    """Valida se a barra de recursos é renderizada sem erros."""
    _render_resource_bar("Test", 50, 100, "green")
    captured = capsys.readouterr()
    assert "Test" in captured.out

def test_analyze_processing_with_hot_lines(capsys):
    """Garante que a análise de processamento lida com JSON de linhas."""
    fake_row = {
        'cpu_percent': 90.0,
        'line_profile_data': json.dumps([
            {'file': 'app.py', 'line': 10, 'hits': 80},
            {'file': 'app.py', 'line': 15, 'hits': 20}
        ])
    }
    
    _analyze_processing_detailed(fake_row)
    captured = capsys.readouterr()
    assert "GARGALOS" in captured.out
    assert "80.0%" in captured.out