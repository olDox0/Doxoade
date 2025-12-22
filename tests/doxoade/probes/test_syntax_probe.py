import sys
import subprocess
import os
from pathlib import Path

# Caminho para a sonda
PROBE_PATH = os.path.join("doxoade", "probes", "syntax_probe.py")

def test_syntax_probe_valid_file(tmp_path):
    """Verifica se código válido passa com exit code 0."""
    f = tmp_path / "good.py"
    f.write_text("def foo():\n    pass", encoding="utf-8")
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(f)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stderr == ""

def test_syntax_probe_invalid_file(tmp_path):
    """Verifica se erro de sintaxe retorna exit code 1 e mensagem formatada."""
    f = tmp_path / "bad.py"
    f.write_text("def foo(\n    pass", encoding="utf-8") # Falta fechar parentese
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(f)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "SyntaxError:" in result.stderr
    assert "bad.py:1" in result.stderr # Deve identificar a linha