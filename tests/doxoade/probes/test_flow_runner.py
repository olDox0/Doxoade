import sys
import subprocess
import os

PROBE_PATH = os.path.join("doxoade", "probes", "flow_runner.py")

def test_flow_runner_execution(tmp_path):
    """Verifica se o flow runner executa um script simples e produz output."""
    script = tmp_path / "ola.py"
    # Usamos ASCII puro para evitar problemas de encoding no Windows durante o teste
    script.write_text("print('Ola Mundo')", encoding="utf-8")
    
    # Força ambiente UTF-8
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(script)],
        capture_output=True, 
        text=True, 
        encoding="utf-8",
        errors="replace", # Tolera erros de decode
        env=env
    )
    
    # Debug se falhar
    if result.stdout is None:
        print(f"STDOUT None! Stderr: {result.stderr}")
        assert False, "Subprocesso não retornou stdout (crash de encoding?)"

    # Verifica se rodou
    assert result.returncode == 0
    assert "Ola Mundo" in result.stdout
    # Verifica se o header do Flow apareceu
    assert "DOXOADE FLOW" in result.stdout
    # Verifica se rastreou a linha
    assert "ola.py:1" in result.stdout