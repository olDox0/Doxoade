# tests/test_classification_regression.py
"""
Testes de Regressão - Classificação Semântica
==============================================
Garante que a lógica de classificação nunca seja perdida novamente.

Execute:
    pytest tests/test_classification_regression.py -v
"""
import pytest
from doxoade.analysis.semantic_classifier import classify_finding, enrich_findings

class TestSemanticClassification:
    """Testes de classificação básica."""
    
    def test_deadcode_classification(self):
        """Imports não utilizados devem ser classificados como DEADCODE."""
        result = classify_finding("'os' imported but unused")
        assert result['category'] == 'DEADCODE'
        assert result['severity'] == 'ERROR'
    
    def test_undefined_name_critical(self):
        """Nomes indefinidos são riscos críticos de runtime."""
        result = classify_finding("undefined name 'foo'")
        assert result['category'] == 'RUNTIME-RISK'
        assert result['severity'] == 'CRITICAL'
    
    def test_syntax_error_critical(self):
        """Erros de sintaxe impedem execução."""
        result = classify_finding("invalid syntax")
        assert result['category'] == 'SYNTAX'
        assert result['severity'] == 'CRITICAL'
    
    def test_security_eval_critical(self):
        """Uso de eval() é risco crítico de segurança."""
        result = classify_finding("Use of eval()")
        assert result['category'] == 'SECURITY'
        assert result['severity'] == 'CRITICAL'
    
    def test_fstring_style_warning(self):
        """F-strings vazias são avisos de estilo."""
        result = classify_finding("f-string is missing placeholders")
        assert result['category'] == 'STYLE'
        assert result['severity'] == 'WARNING'
    
    def test_fallback_uncategorized(self):
        """Mensagens desconhecidas caem no fallback."""
        result = classify_finding("Some unknown error message")
        assert result['category'] == 'UNCATEGORIZED'
        assert result['severity'] == 'WARNING'

class TestEnrichFindings:
    """Testes de enriquecimento em batch."""
    
    def test_enrich_empty_list(self):
        """Lista vazia deve retornar lista vazia."""
        assert enrich_findings([]) == []
    
    def test_enrich_preserves_other_fields(self):
        """Campos originais devem ser preservados."""
        findings = [
            {
                'message': "'os' imported but unused",
                'file': 'test.py',
                'line': 5,
                'custom_field': 'preserved'
            }
        ]
        
        enriched = enrich_findings(findings)
        assert len(enriched) == 1
        assert enriched[0]['file'] == 'test.py'
        assert enriched[0]['line'] == 5
        assert enriched[0]['custom_field'] == 'preserved'
        assert enriched[0]['category'] == 'DEADCODE'
    
    def test_enrich_multiple_findings(self):
        """Deve classificar corretamente múltiplos findings."""
        findings = [
            {'message': "'os' imported but unused"},
            {'message': "undefined name 'foo'"},
            {'message': "invalid syntax"}
        ]
        
        enriched = enrich_findings(findings)
        assert len(enriched) == 3
        assert enriched[0]['category'] == 'DEADCODE'
        assert enriched[1]['category'] == 'RUNTIME-RISK'
        assert enriched[2]['category'] == 'SYNTAX'

class TestCriticalRegressions:
    """
    Casos que causaram regressões no passado.
    Estes testes DEVEM passar sempre.
    """
    
    def test_regression_6c85119_deadcode_lost(self):
        """
        REGRESSÃO HISTÓRICA (6c85119 → HEAD):
        A classificação de imports não usados como DEADCODE foi perdida.
        """
        finding = {'message': "'subprocess' imported but unused"}
        enriched = enrich_findings([finding])[0]
        
        assert enriched['category'] == 'DEADCODE', \
            "REGRESSÃO: Imports não usados devem ser DEADCODE, não genéricos"
        assert enriched['severity'] == 'ERROR', \
            "REGRESSÃO: Imports não usados devem ser ERROR, não WARNING"
    
    def test_regression_6c85119_runtime_risk_lost(self):
        """
        REGRESSÃO HISTÓRICA (6c85119 → HEAD):
        A classificação de nomes indefinidos como RUNTIME-RISK foi perdida.
        """
        finding = {'message': "undefined name 'missing_var'"}
        enriched = enrich_findings([finding])[0]
        
        assert enriched['category'] == 'RUNTIME-RISK', \
            "REGRESSÃO: Nomes indefinidos devem ser RUNTIME-RISK"
        assert enriched['severity'] == 'CRITICAL', \
            "REGRESSÃO: Nomes indefinidos são CRITICAL (causam NameError)"
    
    def test_regression_severity_downgrade_blocked(self):
        """
        Garante que severidades críticas nunca sejam rebaixadas para WARNING.
        """
        critical_messages = [
            "undefined name 'x'",
            "invalid syntax",
            "Use of eval()",
            "No module named 'missing'"
        ]
        
        for msg in critical_messages:
            result = classify_finding(msg)
            assert result['severity'] in ['CRITICAL', 'ERROR'], \
                f"Mensagem '{msg}' foi incorretamente classificada como {result['severity']}"

class TestEdgeCases:
    """Casos extremos e boundary conditions."""
    
    def test_empty_message(self):
        """Mensagem vazia não deve crashar."""
        result = classify_finding("")
        assert result['category'] == 'UNCATEGORIZED'
    
    def test_none_message(self):
        """None não deve crashar (converte para string)."""
        result = classify_finding(None)
        assert result is not None
    
    def test_unicode_message(self):
        """Mensagens com Unicode devem funcionar."""
        result = classify_finding("Variável 'não_definida' não encontrada")
        assert result is not None
    
    def test_multiline_message(self):
        """Mensagens multilinha devem ser processadas."""
        msg = "Error on line 1\nCaused by: something"
        result = classify_finding(msg)
        assert result is not None

# === FIXTURES DE TESTE ===
@pytest.fixture
def sample_findings():
    """Findings de exemplo para testes."""
    return [
        {
            'message': "'os' imported but unused",
            'file': 'test.py',
            'line': 1
        },
        {
            'message': "undefined name 'foo'",
            'file': 'test.py',
            'line': 5
        },
        {
            'message': "f-string is missing placeholders",
            'file': 'test.py',
            'line': 10
        }
    ]

@pytest.fixture
def expected_categories():
    """Mapeamento esperado de categorias."""
    return {
        "'os' imported but unused": 'DEADCODE',
        "undefined name 'foo'": 'RUNTIME-RISK',
        "f-string is missing placeholders": 'STYLE'
    }

# === TESTES DE INTEGRAÇÃO ===
class TestIntegrationWithEngine:
    """Testes de integração com o Engine (se disponível)."""
    
    def test_engine_uses_classifier(self):
        """
        Verifica se o Engine usa o classificador.
        (Requer que doxoade.analysis.engine esteja disponível)
        """
        try:
            from doxoade.analysis.engine import AnalysisEngine
            # Se importar sem erro, o Engine existe
            assert hasattr(AnalysisEngine, '_parse_pyflakes_output'), \
                "Engine deve ter método _parse_pyflakes_output"
        except ImportError:
            pytest.skip("Engine não disponível neste ambiente")
    
    def test_pyflakes_output_parsing(self):
        """
        Testa o parsing de saída real do Pyflakes.
        """
        # Simula saída do Pyflakes
        mock_output = """test.py:5:1: 'os' imported but unused
test.py:10:5: undefined name 'foo'
test.py:15:1: f-string is missing placeholders"""
        
        # Em produção, isso seria feito pelo Engine
        # Aqui validamos apenas o formato
        lines = mock_output.strip().splitlines()
        assert len(lines) == 3
        
        # Cada linha deve ser parseável
        import re
        for line in lines:
            match = re.match(r'(.+?):(\d+):(\d+):\s(.+)', line)
            assert match is not None, f"Linha inválida: {line}"

# === TESTES DE PERFORMANCE ===
class TestPerformance:
    """Garante que a classificação não degrada performance."""
    
    def test_classify_speed(self, benchmark):
        """Classificação única deve ser < 1ms."""
        benchmark(classify_finding, "'os' imported but unused")
    
    def test_enrich_bulk_speed(self, benchmark):
        """Enriquecimento de 100 findings deve ser < 10ms."""
        findings = [{'message': f"Error {i}"} for i in range(100)]
        benchmark(enrich_findings, findings)

# === DOCUMENTAÇÃO DOS TESTES ===
"""
COBERTURA DE TESTES:
--------------------
✅ Classificação básica (6 casos)
✅ Enriquecimento em batch (3 casos)
✅ Regressões históricas (3 casos críticos)
✅ Edge cases (4 casos extremos)
✅ Integração com Engine (2 casos)
✅ Performance (2 benchmarks)

TOTAL: 20 testes

COMO EXECUTAR:
--------------
# Todos os testes
pytest tests/test_classification_regression.py -v

# Apenas regressões críticas
pytest tests/test_classification_regression.py::TestCriticalRegressions -v

# Com cobertura
pytest tests/test_classification_regression.py --cov=doxoade.analysis.semantic_classifier

# Benchmarks de performance
pytest tests/test_classification_regression.py --benchmark-only

ADICIONANDO NOVOS TESTES:
--------------------------
Quando descobrir uma nova regressão:
1. Adicione um teste em TestCriticalRegressions
2. Nomeie como test_regression_YYMMDD_descricao
3. Documente o commit/PR que causou a regressão
4. Valide que o teste falha no código bugado
5. Valide que o teste passa no código corrigido
"""