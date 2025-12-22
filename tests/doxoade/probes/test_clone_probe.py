import sys
import subprocess
import os
import json

PROBE_PATH = os.path.join("doxoade", "probes", "clone_probe.py")

def test_clone_probe_detects_duplication(tmp_path):
    """Verifica se detecta lógica idêntica com nomes diferentes."""
    f1 = tmp_path / "a.py"
    f1.write_text("""
def calc_area(width, height):
    return width * height
""", encoding="utf-8")

    f2 = tmp_path / "b.py"
    f2.write_text("""
def get_size(x, y):
    # Nomes diferentes, mesma AST
    return x * y
""", encoding="utf-8")
    
    payload = json.dumps([str(f1), str(f2)])
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH],
        input=payload,
        capture_output=True, text=True, encoding="utf-8"
    )
    
    data = json.loads(result.stdout)
    assert len(data) >= 2, "Deveria ter encontrado 2 ocorrências (uma em cada arquivo)"
    assert data[0]['category'] == 'DUPLICATION'
    
    # Verifica se os nomes das funções foram citados
    msg = data[0]['message']
    assert "calc_area" in msg or "get_size" in msg