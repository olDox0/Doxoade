import time
# [DOX-UNUSED] import sys
def test():
    t0 = time.perf_counter()
    # Importa nosso módulo novo
    from doxoade.tools.doxcolors import Fore, Style, colors
    
    # O setup do Windows só roda aqui, no primeiro acesso
    print(f"{Fore.GREEN}Teste de Inicialização Lazy{Style.RESET_ALL}")
    
    # Teste TrueColor
    print(f"{colors.hex('#FF00FF')}Este é um texto em Magenta Neon (Hex){Style.RESET_ALL}")
    
    t1 = time.perf_counter()
    print(f"Tempo total (Import + Setup + Print): {(t1-t0)*1000:.4f}ms")
if __name__ == "__main__":
    test()