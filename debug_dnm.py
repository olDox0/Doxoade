# debug_dnm.py
from doxoade.dnm import DNM
import os

print(f"CWD: {os.getcwd()}")
try:
    dnm = DNM(".")
    files = dnm.scan(extensions=['.py'])
    print(f"Total de arquivos encontrados pelo DNM: {len(files)}")
    
    # Verifica se o nightmare está na lista
    found_nightmare = any("nightmare.py" in f for f in files)
    print(f"Nightmare encontrado? {'SIM' if found_nightmare else 'NÃO'}")
    
    if len(files) < 10:
        print("Arquivos:", files)
except Exception as e:
    print(f"ERRO NO DNM: {e}")