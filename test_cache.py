# test_cache.py
import time
import sys
from dataclasses import dataclass

# 1. O Jeito Python Tradicional (Inimigo do Cache)
class ObjetoNormal:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

# 2. O Jeito Cache-Aware (Empacotamento de Memória)
@dataclass(slots=True)
class ObjetoCacheAware:
    x: int
    y: int
    z: int

def run_benchmark():
    elementos = 1_000_000
    print(f"Alocando {elementos} objetos...")

    # --- Teste 1: Objeto Normal ---
    start = time.perf_counter()
    array_normal =[ObjetoNormal(i, i+1, i+2) for i in range(elementos)]
    alloc_normal = time.perf_counter() - start
    
    # Mede iteração (Testa os Cache Misses da CPU)
    start = time.perf_counter()
    soma = 0
    for obj in array_normal:
        soma += obj.x  # CPU tem que buscar o __dict__ do objeto na RAM
    iter_normal = time.perf_counter() - start

    # --- Teste 2: Cache-Aware (Slots) ---
    start = time.perf_counter()
    array_aware =[ObjetoCacheAware(i, i+1, i+2) for i in range(elementos)]
    alloc_aware = time.perf_counter() - start
    
    # Mede iteração (Testa os Cache Hits)
    start = time.perf_counter()
    soma2 = 0
    for obj in array_aware:
        soma2 += obj.x  # CPU lê direto da estrutura empacotada!
    iter_aware = time.perf_counter() - start

    # --- Resultados ---
    print("\n=== RESULTADOS: CELERON TUNNEL ===")
    print("[OBJETO NORMAL (C/ __dict__)]")
    print(f"  Tempo de Alocação : {alloc_normal:.3f} s")
    print(f"  Tempo de Leitura  : {iter_normal:.3f} s (Cache Misses)")
    print(f"  Tamanho na Memória: ~{sys.getsizeof(array_normal[0].__dict__) + sys.getsizeof(array_normal[0])} bytes por objeto")

    print("\n[OBJETO CACHE-AWARE (SLOTS)]")
    print(f"  Tempo de Alocação : {alloc_aware:.3f} s")
    print(f"  Tempo de Leitura  : {iter_aware:.3f} s (Cache Hits)")
    print(f"  Tamanho na Memória: ~{sys.getsizeof(array_aware[0])} bytes por objeto (SEM dict)")

    print(f"\nVelocidade de Leitura melhorada em: {(iter_normal/iter_aware - 1)*100:.1f}%")

if __name__ == "__main__":
    run_benchmark()