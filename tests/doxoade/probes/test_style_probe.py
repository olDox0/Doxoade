import sys
import subprocess
import os
import json

PROBE_PATH = os.path.join("doxoade", "probes", "style_probe.py")

def test_style_probe_detects_long_function(tmp_path):
    """Verifica se função > 60 linhas gera alerta de COMPLEXITY."""
    f = tmp_path / "long.py"
    # Gera função com 70 linhas
    content = "def long_func():\n" + "\n".join([f"    x={i}" for i in range(70)])
    f.write_text(content, encoding="utf-8")
    
    # A sonda de estilo espera um JSON via STDIN com a lista de arquivos
    payload = json.dumps({"files": [str(f)], "comments_only": False})
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH],
        input=payload,
        capture_output=True, text=True, encoding="utf-8"
    )
    
    data = json.loads(result.stdout)
    found = any(f['category'] == 'COMPLEXITY' for f in data)
    assert found, "Style Probe ignorou função longa"

def test_style_probe_detects_missing_docstring(tmp_path):
    """Verifica falta de docstring em função pública."""
    f = tmp_path / "undocumented.py"
    f.write_text("def public_api(): pass", encoding="utf-8")
    
    payload = json.dumps({"files": [str(f)], "comments_only": False})
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH],
        input=payload,
        capture_output=True, text=True, encoding="utf-8"
    )
    
    data = json.loads(result.stdout)
    found = any(f['category'] == 'DOCS' for f in data)
    assert found, "Style Probe ignorou falta de docstring"