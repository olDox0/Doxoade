import sys
import subprocess
import os
import json

PROBE_PATH = os.path.join("doxoade", "probes", "xref_probe.py")

def test_xref_probe_detects_broken_import(tmp_path):
    """Verifica se import de símbolo inexistente é detectado."""
    # Cria arquivo A (biblioteca)
    lib = tmp_path / "lib.py"
    lib.write_text("def existe(): pass", encoding="utf-8")
    
    # Cria arquivo B (consumidor quebrado)
    main = tmp_path / "main.py"
    main.write_text("from lib import nao_existe", encoding="utf-8")
    
    # Payload: Lista de arquivos para analisar
    payload = json.dumps([str(lib), str(main)])
    
    # Passa a RAIZ do projeto como argumento
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(tmp_path)],
        input=payload,
        capture_output=True, text=True, encoding="utf-8"
    )
    
    data = json.loads(result.stdout)
    found = any(f['category'] == 'BROKEN-LINK' and 'nao_existe' in f['message'] for f in data)
    assert found, "XRef Probe falhou em detectar import quebrado"

def test_xref_probe_detects_signature_mismatch(tmp_path):
    """Verifica se chamada com argumentos errados é detectada."""
    f = tmp_path / "sig.py"
    # [CORREÇÃO] Código alinhado à esquerda para evitar IndentationError
    f.write_text("def soma(a, b): return a + b\nsoma(1)", encoding="utf-8")
    
    payload = json.dumps([str(f)])
    
    result = subprocess.run(
        [sys.executable, PROBE_PATH, str(tmp_path)],
        input=payload,
        capture_output=True, text=True, encoding="utf-8"
    )
    
    # Debug: Se falhar, imprime o que veio
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"STDOUT INVÁLIDO: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise

    found = any(f['category'] == 'SIGNATURE-MISMATCH' for f in data)
    assert found, f"XRef Probe falhou. Findings encontrados: {data}"