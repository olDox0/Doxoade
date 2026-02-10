# -*- coding: utf-8 -*-
import time
from colorama import Fore, Style
from heavy_core import compute_chunk
from doxoade.tools.vulcan.bridge import vulcan_bridge

def run_benchmark():
    print(f"{Fore.CYAN}🚀 [VULCAN-BENCHMARK] Comparando Python vs. Metal Nativo...{Fore.RESET}")
    
    N = 10_000_000 # 10 milhões de iterações
    
    # 1. Teste Python Puro
    print(f"   {Fore.WHITE}Executando Python Puro...")
    t0 = time.perf_counter()
    res_py = compute_chunk(N)
    d_py = time.perf_counter() - t0
    print(f"   > Tempo: {d_py:.4f}s")

    # 2. Teste Vulcan (Via Bridge)
    print(f"\n   {Fore.WHITE}Buscando otimização Vulcano...")
    native_compute = vulcan_bridge.get_optimized("heavy_core", "compute_chunk")
    
    if not native_compute:
        print(f"   {Fore.RED}✘ Falha: Binário não encontrado ou incompatível.{Fore.RESET}")
        return

    print(f"   {Fore.GREEN}✔ Binário carregado com sucesso. Iniciando execução nativa...")
    t1 = time.perf_counter()
    res_v = native_compute(N)
    d_v = time.perf_counter() - t1
    print(f"   > Tempo: {d_v:.4f}s")

    # 3. Veredito Industrial
    speedup = d_py / d_v
    print(f"\n{Fore.CYAN}{Style.BRIGHT}--- RELATÓRIO DE IMPACTO ---{Style.RESET_ALL}")
    print(f"   Aceleração: {Fore.GREEN}{Style.BRIGHT}{speedup:.1f}x mais rápido{Fore.RESET}")
    
    if res_py == res_v:
        print(f"   Integridade: {Fore.GREEN}100% (Equivalência de Bits OK){Fore.RESET}")
    else:
        print(f"   Integridade: {Fore.RED}FALHA (Divergência matemática!){Fore.RESET}")

if __name__ == "__main__":
    run_benchmark()