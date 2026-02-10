# -*- coding: utf-8 -*-
# tests/vulcan_sandbox/test_forge.py
"""
Doxoade Vulcan Stress Test - Bitwise Cipher.
Simula complexidade de baixo nível para forçar ignição do Autopilot.
"""

def heavy_bitwise_process(n, seed):
    """Algoritmo de crunching de bits para teste de performance nativa."""
    # Variáveis que o Forge deve tipar como 'long'
    result = seed
    
    for i in range(n):
        # Sequência complexa de mutação de bits
        # Python precisa criar novos objetos para cada operação
        # Vulcan (C) fará isso diretamente nos registradores
        result = ((result << 1) ^ i) & 0xFFFFFFFF
        result = (result >> 1) | (i << 16)
        result = (result ^ 0xDEADBEEF) & 0xFFFFFFFF
        
        if i % 3 == 0:
            result = (result + i) & 0xFFFFFFFF
        elif i % 2 == 0:
            result = (result - 1) & 0xFFFFFFFF
            
    return result

if __name__ == "__main__":
    # 10 milhões de iterações para gerar calor nítido
    ITERACOES = 10000000
    SEED_INICIAL = 12345
    
    print(f"--- VULCAN STRESS TEST ---")
    print(f"Iniciando crunching de {ITERACOES:,} iterações...")
    
    import time
    start = time.perf_counter()
    res = heavy_bitwise_process(ITERACOES, SEED_INICIAL)
    end = time.perf_counter()
    
    print(f"Resultado: {res}")
    print(f"Tempo de Execução (Python): {end - start:.4f}s")