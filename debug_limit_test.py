# debug_limit_test.py
import time

print("[*] Iniciando alocação pesada...")
try:
    # Tenta criar uma lista de 100 milhões de inteiros (~800MB+ de RAM)
    lixo = [i for i in range(100_000_000)]
    print("[OK] Alocação concluída com sucesso.")
except Exception as e:
    print(f"[!] Erro: {e}")