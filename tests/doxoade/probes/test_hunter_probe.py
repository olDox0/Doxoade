import sys
import subprocess
import os
import json

PROBE_PATH = os.path.join("doxoade", "probes", "hunter_probe.py")

def test_hunter_detects_eval(tmp_path):
    """Verifica se uso de eval é detectado como CRITICAL SECURITY."""
    f = tmp_path / "risky.py"
    f.write_text("x = eval('input()')", encoding="utf-8")
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(f)],
        capture_output=True, text=True
    )
    
    assert result.returncode == 0 # Hunter roda com sucesso, mas reporta erros no JSON
    data = json.loads(result.stdout)
    
    # Procura o finding específico
    found = any(f['category'] == 'SECURITY' and 'eval' in f['message'] for f in data)
    assert found, "Hunter não detectou 'eval'"

def test_hunter_detects_mutable_arg(tmp_path):
    """Verifica argumento mutável."""
    f = tmp_path / "mutable.py"
    f.write_text("def foo(x=[]): pass", encoding="utf-8")
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(f)],
        capture_output=True, text=True
    )
    
    data = json.loads(result.stdout)
    found = any(f['category'] == 'RISK-MUTABLE' for f in data)
    assert found, "Hunter não detectou argumento padrão mutável"