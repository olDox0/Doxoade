# check_vax.py
import os
from pathlib import Path
vax_file = Path(".doxoade/metalcraft/shadow/tnse_engine/race_lab.c")
if vax_file.exists():
    print(f"--- [ INSPEÇÃO DE VACINA: {vax_file.name} ] ---")
    content = vax_file.read_text()
    for i, line in enumerate(content.splitlines()):
        if "soteria_" in line:
            print(f"L{i+1}: {line.strip()}")
else:
    print("❌ Arquivo de sombra não encontrado. O build falhou ou o caminho mudou.")