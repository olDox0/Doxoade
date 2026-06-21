# doxoade/commands/macrothon_systems/macrothon_diag.py
import re
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from doxoade.tools.doxcolors import Fore

# O Blueprint que você escreveu
blueprint = """
IMPORT { acervo mergesort_python:mergeSort as MERGESORT }
TREE { servicos/ mergesort_python }

raw_data = [3, 7, 6, -10]
print("DEBUG: Iniciando House...")

MERGESORT:
    input = raw_data
    output = result

print("DEBUG: Resultado final -> " + str(result))
"""

print("--- [SIMULAÇÃO DE TRADUÇÃO MACROTHON] ---")

# 1. Teste da Regex (Cena do Crime)
def translate(match):
    name, body = match.group(1), match.group(2)
    in_v = re.search(r"input\s*=\s*([\w\[\].]+)", body).group(1)
    out_v = re.search(r"output\s*=\s*([\w\[\].]+)", body).group(1)
    return f"{out_v} = {name}({in_v})\\n"

code_clean = re.sub(r"(\w+):\s*\\n\s*((?:.|\n)*?)(?=\n\S|$)", translate, blueprint)
code_clean = re.sub(r"IMPORT\s*\{.*?\}", "", code_clean, flags=re.DOTALL)
code_clean = re.sub(r"TREE\s*\{.*?\}", "", code_clean, flags=re.DOTALL)

print(f"CÓDIGO TRADUZIDO:\n{code_clean}")

# 2. Teste de Execução
print("\n--- [TESTE DE EXECUÇÃO] ---")
ctx = {
    'print': print, 'str': str, 'Fore': Fore,
    'MERGESORT': lambda x: sorted(x) # Simula o brick
}

try:
    restricted_safe_exec(code_clean, ctx)
    print("\n[OK] Simulação concluída.")
except Exception as e:
    print(f"\n[FALHA] Erro na execução: {e}")