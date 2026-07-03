# test_hermes_real_gain.py - Versão Corrigida
import time
import sys
import subprocess
from pathlib import Path

def measure_module_load(module_name: str, use_hermes: bool) -> float:
    """Mede tempo de carregar um módulo específico em subprocesso isolado."""
    if use_hermes:
        script = f"""
import sys
import time
import os

# Desabilita logs do Hermes
os.environ['HERMES_VERBOSE'] = '0'

# Instala o hook do Hermes
try:
    from doxoade.tools.hermes_systems.hermes_hook import install
    install('.')
except Exception as e:
    print(f"ERRO: {{e}}", file=sys.stderr)
    sys.exit(1)

# Mede o tempo de import
start = time.perf_counter()
try:
    import {module_name}
    duration = (time.perf_counter() - start) * 1000
    # Apenas o número, sem logs
    print(f"{{duration:.3f}}")
except Exception as e:
    print(f"ERRO_IMPORT: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    else:
        script = f"""
import sys
import time

# Mede o tempo de import sem Hermes
start = time.perf_counter()
try:
    import {module_name}
    duration = (time.perf_counter() - start) * 1000
    print(f"{{duration:.3f}}")
except Exception as e:
    print(f"ERRO_IMPORT: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path.cwd()),
            env={**os.environ, 'HERMES_VERBOSE': '0'}  # ← CRÍTICO
        )
        
        if result.returncode != 0:
            return 0.0
        
        # Extrai apenas a última linha (o número)
        stdout = result.stdout.strip()
        if not stdout:
            return 0.0
        
        # Pega apenas a última linha (ignora logs)
        lines = stdout.split('\n')
        duration_str = lines[-1].strip()
        
        return float(duration_str)
        
    except (subprocess.TimeoutExpired, ValueError) as e:
        return 0.0

# Testa módulos críticos
modules = [
    'doxoade.cli',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.vulcan.compiler',
]

print("Módulo                                    | Python  | Hermes  | Speedup")
print("-" * 75)

for mod in modules:
    py_time = measure_module_load(mod, use_hermes=False)
    hermes_time = measure_module_load(mod, use_hermes=True)
    
    if py_time > 0 and hermes_time > 0:
        speedup = py_time / hermes_time
        status = "✅" if speedup > 1.0 else "❌"
        print(f"{mod:40} | {py_time:6.2f}ms | {hermes_time:6.2f}ms | {speedup:.2f}× {status}")
    else:
        print(f"{mod:40} | {py_time:6.2f}ms | {hermes_time:6.2f}ms | N/A ⚠️")