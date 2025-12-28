# Adicione ao final do arquivo, ou substitua o conteúdo:

import random

FUNCOES = [
    "soma", "sub", "mult", "div", "maior", 
    "adicionar", "adição", "somar", "mais",
    "calcular", "processar",
    # [NOVO] Verbos de I/O
    "salvar", "ler", "escrever", "gravar", "carregar"
]
VARIAVEIS = ["a", "b", "x", "y", "val", "num", "dado", "valor", "texto", "conteudo", "arquivo"]
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
    f = random.choice(FUNCOES)
    v = random.choice(VARIAVEIS)
    return f"def {f} ( {v} ) : if {v} : return True else : return False"

# [NOVO] Padrão de I/O
def gerar_funcao_io():
    acao = random.choice(["salvar", "escrever", "gravar"])
    var = random.choice(["texto", "dados", "conteudo"])
    # Ensina o padrão 'with open'
    return f"def {acao}_{var} ( {var} ) : with open ( 'file.txt' , 'w' ) as f : f.write ( {var} )"

# [NOVO] Atualiza o vocabulário
def obter_vocabulario_completo():
    tokens = ["def", "(", ")", ":", "return", ",", "pass", "<PAD>", "<UNK>", "ENDMARKER"]
    tokens += ["if", "else", "elif", "True", "False", "None"] 
    tokens += ["with", "open", "as", "f", "write", "read", "'w'", "'r'", "'file.txt'", "."] # Tokens de I/O
    tokens += FUNCOES + VARIAVEIS + OPS 
    return list(set(tokens))