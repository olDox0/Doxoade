import os  # [DEADCODE] Importado mas não usado
import sys
import hashlib
import subprocess
import pickle
import modulo_fantasma_xyz  # [DEPENDENCY] Import que não existe

# [STYLE] Variável global
SENHA_MESTRE = "admin123"  # [SECURITY] Senha Hardcoded

def funcao_perigosa(dados=[]):  # [RISK-MUTABLE] Argumento padrão mutável
    # [DOCS] Falta docstring
    
    # [DEADCODE] Variável inútil
    x = 10 
    
    # [STYLE] Comparação com None
    if dados == None:
        return

    # [RISK-EXCEPTION] Except genérico
    try:
        # [SECURITY] Execução arbitrária
        eval("print('hackeado')")
        
        # [SECURITY] Shell Injection
        subprocess.run("rm -rf /", shell=True)
        
        # [SECURITY] Hash fraco
        h = hashlib.md5(b"texto")
        
        # [SECURITY] Deserialização insegura
        pickle.loads(b"cos\nsystem\n(S'ls'\ntR.")
        
    except:
        pass

    # [ABDUÇÃO] 'math' e 'random' não foram importados
    print(math.pi)
    print(random.randint(1, 10))

    # [STYLE] Recursão
    funcao_perigosa(dados)

def funcao_gigante_e_complexa():
    # [COMPLEXITY] Função muito longa (MPoT)
    print("Linha 1")
    print("Linha 2")
    print("Linha 3")
    print("Linha 4")
    print("Linha 5")
    print("Linha 6")
    print("Linha 7")
    print("Linha 8")
    print("Linha 9")
    print("Linha 10")
    print("Linha 11")
    print("Linha 12")
    print("Linha 13")
    print("Linha 14")
    print("Linha 15")
    print("Linha 16")
    print("Linha 17")
    print("Linha 18")
    print("Linha 19")
    print("Linha 20")
    print("Linha 21")
    print("Linha 22")
    print("Linha 23")
    print("Linha 24")
    print("Linha 25")
    print("Linha 26")
    print("Linha 27")
    print("Linha 28")
    print("Linha 29")
    print("Linha 30")
    print("Linha 31")
    print("Linha 32")
    print("Linha 33")
    print("Linha 34")
    print("Linha 35")
    print("Linha 36")
    print("Linha 37")
    print("Linha 38")
    print("Linha 39")
    print("Linha 40")
    print("Linha 41")
    print("Linha 42")
    print("Linha 43")
    print("Linha 44")
    print("Linha 45")
    print("Linha 46")
    print("Linha 47")
    print("Linha 48")
    print("Linha 49")
    print("Linha 50")
    print("Linha 51")
    print("Linha 52")
    print("Linha 53")
    print("Linha 54")
    print("Linha 55")
    print("Linha 56")
    print("Linha 57")
    print("Linha 58")
    print("Linha 59")
    print("Linha 60")
    print("Linha 61")
    print("Linha 62")
    pass
    
# doxoade/commands/nightmare.py
def bug_fatal():
    eval("print('Eu sou um erro de seguranca no core!')")

# [DUPLICATION] Função clonada (igual a funcao_perigosa mas com nome diferente)
def clone_da_perigosa(dados=[]):
    # [DOCS] Falta docstring
    x = 10 
    if dados == None: return
    try:
        eval("print('hackeado')")
        subprocess.run("rm -rf /", shell=True)
        h = hashlib.md5(b"texto")
        pickle.loads(b"cos\nsystem\n(S'ls'\ntR.")
    except: pass
    print(math.pi)
    print(random.randint(1, 10))
    funcao_perigosa(dados)

# [SIGNATURE-MISMATCH] Chamada incorreta (XRef)
def teste_assinatura(a, b):
    return a + b

teste_assinatura(1) # Falta argumento 'b'

import os
import sys

def funcao_horrivel():
    try:
        eval("print('hack')") # SECURITY
    except: # RISK-EXCEPTION
        pass
    
    x = 10 # DEADCODE