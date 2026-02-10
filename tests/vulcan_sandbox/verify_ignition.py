# -*- coding: utf-8 -*-
import sys
import os
import time
import importlib.util
from colorama import Fore, Style

def test_equivalence():
    print(f"{Fore.CYAN}🧪 [VULCAN-LAB] Iniciando Prova de Equivalência...{Fore.RESET}")
    
    # 1. Definição da Função Original (Python)
    def heavy_math_py(n):
        total = 0.0
        for i in range(n):
            total += i * 1.5
        return total

    # 2. Carregamento Dinâmico do Binário Vulcano
    bin_path = os.path.abspath(".doxoade/vulcan/bin/v_test_forge.pyd")
    spec = importlib.util.spec_from_file_location("v_test_forge", bin_path)
    v_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v_module)

    # 3. Teste de Stress e Precisão
    N = 1_000_000
    
    # Execução Python
    t0 = time.perf_counter()
    res_py = heavy_math_py(N)
    d_py = time.perf_counter() - t0
    
    # Execução Nativa (Vulcano)
    # Note: O nome da função gerada é {original}_vulcan_optimized
    t1 = time.perf_counter()
    res_v = v_module.heavy_math_vulcan_optimized(N)
    d_v = time.perf_counter() - t1

    # 4. Relatório Nexus Gold
    print(f"\n   Alvo: heavy_math (N={N:,})")
    print(f"   Python Time  : {Fore.YELLOW}{d_py:.5f}s")
    print(f"   Vulcan Time  : {Fore.GREEN}{d_v:.5f}s")
    
    speedup = d_py / d_v
    print(f"   Speedup      : {Style.BRIGHT}{speedup:.1f}x mais rápido")

    if res_py == res_v:
        print(f"\n{Fore.GREEN}✔ [SUCESSO] Equivalência de Bits confirmada.")
        print(f"   Resultado: {res_v}")
    else:
        print(f"\n{Fore.RED}✘ [FALHA] Divergência Lógica Detectada!")
        print(f"   Py: {res_py} | Vulcan: {res_v}")

if __name__ == "__main__":
    test_equivalence()