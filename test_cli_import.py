# test_cli_import.py
import time
import sys

print("Iniciando import do cli.py...")
t0 = time.perf_counter()

# Isso vai forçar o Python a carregar o cli.py e todas as suas dependências de nível de módulo
from doxoade.cli import cli 

t1 = time.perf_counter()
print(f"✔ Import de cli.py concluído em: {(t1-t0)*1000:.2f} ms")
