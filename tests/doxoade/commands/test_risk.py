# -*- coding: utf-8 -*-
import pytest
from doxoade.commands.risk import calculate_density_penalty

def test_density_penalty_calculation():
    """Valida se o cálculo de densidade estatística está correto."""
    metrics = {
        'total_files': 100,
        'by_category': {
            'SYNTAX': 10,  # 10% da base com erro de sintaxe
            'DEADCODE': 50 # 50% da base com deadcode
        }
    }
    
    penalties = calculate_density_penalty(metrics)
    
    # Sintaxe: (10/100) * 100 = 10 pontos
    syntax_pen = next(p for p in penalties if p['name'] == 'SYNTAX')
    assert syntax_pen['penalty'] == 10.0
    
    # Deadcode: (50/100) * 10 = 5 pontos
    dead_pen = next(p for p in penalties if p['name'] == 'DEADCODE')
    assert dead_pen['penalty'] == 5.0

def test_risk_contract_violation():
    """Garante que a lógica de risco trava sem dados (MPoT-5)."""
    # FIX: Ajustado match para "inválida" para bater com a mensagem do código
    with pytest.raises(ValueError, match="Métricas inválidas"):
        calculate_density_penalty({})

def test_risk_metrics_structure():
    """Verifica se o retorno das penalidades segue o schema esperado."""
    metrics = {'total_files': 10, 'by_category': {'STYLE': 1}}
    res = calculate_density_penalty(metrics)
    assert 'density_pct' in res[0]
    assert 'penalty' in res[0]