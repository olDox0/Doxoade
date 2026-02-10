# -*- coding: utf-8 -*-
# tests/vulcan_sandbox/master_stress.py
import time
from heavy_core import compute_chunk

def run_stress_test():
    print("🚀 [MASTER] Iniciando bombardeio de processamento...")
    total = 0.0
    
    # Chama a função pesada 50 vezes
    for i in range(50):
        print(f"   > Lote {i+1}/50...")
        total += compute_chunk(1000000) # 1 milhão por lote
        
    print(f"🔥 Resultado Final: {total}")

if __name__ == "__main__":
    run_stress_test()