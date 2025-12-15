"""
CODEX GENERATOR v2.0 (Logic Branching).
Gera código Python com fluxo de controle (if/else).
"""
import random

FUNCOES = ["soma", "sub", "mult", "div", "maior", "menor", "check", "validar"]
VARIAVEIS = ["a", "b", "x", "y", "val", "num", "limite"]
OPS = ["+", "-", "*", "/", "%"]
COMPS = [">", "<", "==", "!=", ">=", "<="]

def gerar_funcao_simples():
    f = random.choice(FUNCOES)
    v1 = random.choice(VARIAVEIS)
    v2 = random.choice(VARIAVEIS)
    while v2 == v1: v2 = random.choice(VARIAVEIS)
    op = random.choice(OPS)
    return f"def {f} ( {v1} , {v2} ) : return {v1} {op} {v2}"

def gerar_funcao_condicional():
    """Gera função com IF/ELSE one-liner."""
    # Ex: def maior ( a , b ) : return a if a > b else b
    # Ou estilo bloco simplificado: if a > b : return a else : return b
    
    f = random.choice(["maior", "menor", "check", "test"])
    v1 = random.choice(VARIAVEIS)
    v2 = random.choice(VARIAVEIS)
    while v2 == v1: v2 = random.choice(VARIAVEIS)
    comp = random.choice(COMPS)
    
    # Vamos ensinar o estilo Pythonico ternário primeiro, pois é mais fácil para a LSTM (linear)
    # Mas vamos tentar o estilo bloco linearizado também
    
    tipo = random.choice(["ternario", "bloco"])
    
    if tipo == "ternario":
        return f"def {f} ( {v1} , {v2} ) : return {v1} if {v1} {comp} {v2} else {v2}"
    else:
        return f"def {f} ( {v1} , {v2} ) : if {v1} {comp} {v2} : return {v1} else : return {v2}"

def obter_vocabulario_completo():
    tokens = ["def", "(", ")", ":", "return", ",", "<PAD>", "<UNK>", "ENDMARKER"]
    tokens += ["if", "else", "elif", "True", "False", "None"] 
    tokens += FUNCOES + VARIAVEIS + OPS + COMPS
    return list(set(tokens))