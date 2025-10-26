# tests/test_deepcheck_command.py
import os
import sys
import ast

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.commands.deepcheck import _find_returns_and_risks

def test_deepcheck_finds_dictionary_risk():
    """
    Valida se a lógica do deepcheck detecta um acesso inseguro a um dicionário.
    """
    # FLUXO 1: Preparar o Código "Doente" como uma AST
    risky_code = """
def process_data(data):
    # Ponto de risco: Acesso direto que pode causar KeyError
    name = data['name']
    return name
"""
    tree = ast.parse(risky_code)
    # A função de análise espera a AST do nó da função, não da árvore inteira
    function_node = tree.body[0]

    # FLUXO 2: Executar a Função Alvo Diretamente
    returns, risks = _find_returns_and_risks(function_node)

    # FLUXO 3: Validar o Diagnóstico
    assert len(risks) == 1, "Deveria ter sido encontrado exatamente um ponto de risco."
    
    risk = risks[0]
    assert risk['message'] == "Acesso a dicionário/lista sem tratamento."
    assert "pode causar 'KeyError' ou 'IndexError'" in risk['details']
    assert risk['lineno'] == 4 # A linha onde o acesso inseguro ocorre

    # Valida também que o ponto de retorno foi encontrado
    assert len(returns) == 1
    assert returns[0]['lineno'] == 5