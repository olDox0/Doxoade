# tests/test_guicheck_command.py
import os
import sys
import ast

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.commands.guicheck import _analyze_tkinter_layout

def test_guicheck_finds_mixed_layout_and_weight_issues():
    """
    Valida se a lógica do guicheck detecta tanto o uso misto de gerenciadores
    quanto a falta de configuração de 'weight' no grid.
    """
    # FLUXO 1: Preparar o Código "Doente" como uma AST
    invalid_code = """
import tkinter as tk
root = tk.Tk()
frame = tk.Frame(root)
label1 = tk.Label(frame, text="Hello")
label2 = tk.Label(frame, text="World")
label1.pack()
label2.grid(row=0, column=0) # Erro 1: pack e grid no mesmo pai 'frame'
# Erro 2 (implícito): 'frame' usa grid mas não tem weight configurado
frame.pack()
"""
    tree = ast.parse(invalid_code)

    # FLUXO 2: Executar a Função Alvo Diretamente
    findings = _analyze_tkinter_layout(tree, "fake_file.py")

    # FLUXO 3: Validar os Diagnósticos
    assert len(findings) == 2, f"Esperado 2 findings, mas foram encontrados {len(findings)}."
    
    # Extrai as mensagens para facilitar a validação
    messages = [f['message'] for f in findings]
    
    # Valida que ambos os erros esperados estão presentes
    assert "Uso misto de gerenciadores (pack, grid) no pai 'frame'" in messages[0]
    assert "Pai 'frame' usa .grid() mas não configura 'weight'." in messages[1]
    
    # Valida a severidade de cada um
    assert findings[0]['severity'] == 'ERROR'
    assert findings[1]['severity'] == 'WARNING'