# .doxoade/npp_integration_script.py
from Npp import editor, notepad
import json, os

def on_bridge_change():
    bridge_path = r"C:\seu_projeto\.doxoade\npp_bridge.json"
    with open(bridge_path, 'r') as f:
        data = json.load(f)
    
    # Limpa indicadores antigos
    editor.setIndicatorCurrent(0)
    editor.indicatorClearRange(0, editor.getTextLength())

    for f in data['findings']:
        line = f['line'] - 1
        start = editor.positionFromLine(line)
        length = editor.lineLength(line)
        
        # Pinta a linha conforme MPoT-5.3
        editor.indicatorFillRange(start, length)

# O script fica rodando em background no N++