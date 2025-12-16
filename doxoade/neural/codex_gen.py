"""
CODEX GENERATOR v6.0 (Polyglot Explicit).
"""
import random

FUNCOES = [
    "soma", "sub", "mult", "div", "maior", 
    "adicionar", "adição", "somar", "mais", # Português
    "calcular", "processar"
]
VARIAVEIS = ["a", "b", "x", "y", "val", "num", "dado", "valor"]
OPS = ["+", "-", "*", "/", "%"]

def gerar_sintaxe_basica():
    f = random.choice(FUNCOES)
    v1 = random.choice(VARIAVEIS)
    return f"def {f} ( {v1} ) : pass"

def gerar_funcao_simples():
    f = random.choice(FUNCOES)
    v1 = random.choice(VARIAVEIS)
    v2 = random.choice(VARIAVEIS)
    while v2 == v1: v2 = random.choice(VARIAVEIS)
    op = random.choice(OPS)
    return f"def {f} ( {v1} , {v2} ) : return {v1} {op} {v2}"

def gerar_funcao_condicional():
    return gerar_funcao_simples() # Simplificando para focar no sucesso imediato

def obter_vocabulario_completo():
    tokens = ["def", "(", ")", ":", "return", ",", "pass", "<PAD>", "<UNK>", "ENDMARKER"]
    tokens += ["if", "else", "elif", "True", "False", "None"] 
    tokens += FUNCOES + VARIAVEIS + OPS 
    return list(set(tokens))