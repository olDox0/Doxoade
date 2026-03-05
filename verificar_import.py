# verificar_import.py (Versão Corrigida para Submódulos)
import click
# [DOX-UNUSED] import os

# O 'import click' inicial carrega o pacote. É DENTRO dele que a mágica acontece.
# Agora, vamos acessar um submódulo que sabemos que foi compilado.
# Acessar 'click.formatting' força o Python a tentar importar esse submódulo.
try:
    from click import formatting
    print("--- Verificando o submódulo 'click.formatting' ---")

    caminho_do_submodulo = formatting.__file__

    print("O submódulo 'click.formatting' está sendo carregado de:")
    print(f"  -> {caminho_do_submodulo}")

    if '.doxoade' in caminho_do_submodulo and 'vulcan' in caminho_do_submodulo:
        print("\n\033[92m[SUCESSO] A versão compilada (nativa) do Vulcan está em uso!\033[0m")
        if caminho_do_submodulo.endswith('.pyd') or caminho_do_submodulo.endswith('.so'):
            print("O tipo de arquivo é um binário compilado, como esperado.")
    else:
        print("\n\033[91m[FALHA] A versão padrão em Python (.py) ainda está em uso.\033[0m")

except Exception as e:
    print(f"\n\033[91m[ERRO] Falha ao tentar importar ou inspecionar o submódulo: {e}\033[0m")

    
import click.formatting
import time

# Verifica origem real da função
print(f"wrap_text.__module__: {click.formatting.wrap_text.__module__}")
print(f"wrap_text qualname:   {getattr(click.formatting.wrap_text, '__qualname__', 'N/A')}")

# Vê o que existe no namespace do .pyd carregado como módulo nativo
import sys
native = sys.modules.get('v_formatting_da684d')
if native:
    print("\nNativo encontrado em sys.modules:")
    for name in dir(native):
        if 'wrap' in name or 'iter' in name:
            print(f"  {name}: {type(getattr(native, name)).__name__}")
else:
    print("\nNativo NÃO está em sys.modules — injeção não ocorreu")

# Timing simples
t0 = time.perf_counter()
for _ in range(10000):
    click.formatting.wrap_text("Hello world this is a test string for wrapping", width=40)
elapsed = time.perf_counter() - t0
print(f"\n10k execuções: {elapsed*1000:.1f}ms")