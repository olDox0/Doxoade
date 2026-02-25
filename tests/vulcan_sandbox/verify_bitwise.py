# -*- coding: utf-8 -*-
import sys
import os
import time
import importlib.util
from tools.doxcolors import Fore, Style
def run_vanguard_test():
    print(f"{Fore.CYAN}🧪 [VULCAN-LAB] Iniciando Prova de Bits Vanguard...{Fore.RESET}")
    
    # 1. Definição da Função Original (Python)
    def heavy_bitwise_process_py(n, seed):
        result = seed
        for i in range(n):
            result = ((result << 1) ^ i) & 0xFFFFFFFF
            result = (result >> 1) | (i << 16)
            result = (result ^ 0xDEADBEEF) & 0xFFFFFFFF
            if i % 3 == 0:
                result = (result + i) & 0xFFFFFFFF
            elif i % 2 == 0:
                result = (result - 1) & 0xFFFFFFFF
        return result
    # 2. Carregamento do Metal (Vulcano)
    bin_path = os.path.abspath(".doxoade/vulcan/bin/v_test_forge.pyd")
    spec = importlib.util.spec_from_file_location("v_test_forge", bin_path)
    v_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v_mod)
    # 3. Benchmark de Alta Intensidade
    N = 10_000_000 # 10 Milhões de iterações
    SEED = 12345
    print(f"   Alvo: heavy_bitwise_process (N={N:,})")
    
    # Execução Python
    t0 = time.perf_counter()
    res_py = heavy_bitwise_process_py(N, SEED)
    d_py = time.perf_counter() - t0
    print(f"   Python Time  : {Fore.YELLOW}{d_py:.5f}s")
    # Execução Vanguard (C puro)
    t1 = time.perf_counter()
    res_v = v_mod.heavy_bitwise_process_vulcan_optimized(N, SEED)
    d_v = time.perf_counter() - t1
    print(f"   Vulcan Time  : {Fore.GREEN}{d_v:.5f}s")
    # 4. Veredito Gold
    speedup = d_py / d_v
    print(f"\n{Fore.CYAN}{Style.BRIGHT}--- RELATÓRIO VANGUARD ---{Style.RESET_ALL}")
    print(f"   Aceleração: {Fore.GREEN}{Style.BRIGHT}{speedup:.1f}x mais rápido")
    if res_py == res_v:
        print(f"   Integridade: {Fore.GREEN}✔ 100% (Bit-Wise Match)")
        print(f"   Hash Final : {res_v}")
    else:
        print(f"   Integridade: {Fore.RED}✘ FALHA (Divergência de bits!)")
        print(f"   Py: {res_py} | Vulcan: {res_v}")
if __name__ == "__main__":
    run_vanguard_test()