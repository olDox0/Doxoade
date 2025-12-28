# lab_tokenizer.py
from doxoade.neural.alfagold.tokenizer import AlfagoldTokenizer
from colorama import init, Fore

init(autoreset=True)

print(Fore.YELLOW + "🧠 [LAB] Testando Tokenizer BPE Alfagold...\n")

# 1. Corpus de Treino (Pequeno exemplo de código)
corpus = """
def salvar_arquivo(nome):
    with open(nome, 'w') as f:
        f.write('teste')
def ler_arquivo(nome):
    return open(nome).read()
import os
import sys
"""

tok = AlfagoldTokenizer()
# Treina com vocabulário pequeno para forçar merges interessantes
tok.train(corpus, vocab_size=300) 

print(Fore.CYAN + "\n🔍 Teste de Inferência:")
testes = [
    "def salvar",       # Deve reconhecer 'def' e 'salvar'
    "import os",        # Deve reconhecer 'import'
    "salvar_arquivo",   # O teste de fogo: deve quebrar em 'salvar', '_', 'arquivo' ou similar
]

for t in testes:
    encoded = tok.encode(t)
    print(f"   '{t}' -> {encoded}")

print(Fore.GREEN + "\n✅ Concluído. Se os IDs se repetem para palavras iguais, o BPE funcionou.")