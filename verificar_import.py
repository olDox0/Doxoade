# verificar_import.py (Versão Corrigida para Submódulos)
import click
import os

# O 'import click' inicial carrega o pacote. É DENTRO dele que a mágica acontece.
# Agora, vamos acessar um submódulo que sabemos que foi compilado.
# Acessar 'click.formatting' força o Python a tentar importar esse submódulo.
try:
    from click import formatting
    print("--- Verificando o submódulo 'click.formatting' ---")

    caminho_do_submodulo = formatting.__file__

    print(f"O submódulo 'click.formatting' está sendo carregado de:")
    print(f"  -> {caminho_do_submodulo}")

    if '.doxoade' in caminho_do_submodulo and 'vulcan' in caminho_do_submodulo:
        print("\n\033[92m[SUCESSO] A versão compilada (nativa) do Vulcan está em uso!\033[0m")
        if caminho_do_submodulo.endswith('.pyd') or caminho_do_submodulo.endswith('.so'):
            print("O tipo de arquivo é um binário compilado, como esperado.")
    else:
        print("\n\033[91m[FALHA] A versão padrão em Python (.py) ainda está em uso.\033[0m")

except Exception as e:
    print(f"\n\033[91m[ERRO] Falha ao tentar importar ou inspecionar o submódulo: {e}\033[0m")