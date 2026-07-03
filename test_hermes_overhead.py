# test_hermes_overhead.py
import time
import sys
from pathlib import Path

# Teste 1: Import direto (sem hook)
print("=== Teste 1: Import direto (sem hook) ===")
t0 = time.perf_counter()
import doxoade.cli
t1 = time.perf_counter()
print(f"Tempo: {(t1-t0)*1000:.2f}ms")

# Limpa módulos
for mod in list(sys.modules.keys()):
    if mod.startswith('doxoade'):
        del sys.modules[mod]

# Teste 2: Import com hook ativo
print("\n=== Teste 2: Import com hook ativo ===")
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')

t0 = time.perf_counter()
import doxoade.cli
t1 = time.perf_counter()
print(f"Tempo: {(t1-t0)*1000:.2f}ms")

# Teste 3: Verifica se o hook está realmente carregando .hermes
print("\n=== Teste 3: Verificação de carregamento ===")
from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
loader = HermesLoader('.')
hermes_path = loader.find_hermes_for_module('doxoade.cli')
print(f"Arquivo .hermes existe: {hermes_path.exists() if hermes_path else False}")
if hermes_path and hermes_path.exists():
    print(f"Tamanho: {hermes_path.stat().st_size} bytes")
    print(f"Magic: {hermes_path.read_bytes()[:4]}")