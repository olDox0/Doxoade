# doxoade/diagnostic/check_exame.py
import os  # [DEADCODE]
import sys # [DEADCODE]

def funcao_complexa(a):
    """Gera aviso de complexidade se houver muitos desvios."""
    if a > 1:
        if a > 2:
            if a > 3:
                for i in range(a):
                    while True: break
    return a

def risco_seguranca():
    # [SECURITY]
    eval("print('vulneravel')")

def erro_runtime():
    # [RUNTIME-RISK]
    return variavel_inexistente + 10

def argumento_mutavel(lista=[]): # [RISK-MUTABLE]
    return lista
    
def teste_contrato(valor):
    if valor is None:
        raise ValueError("Contrato: valor não pode ser nulo") # Agora o deepcheck aceita isso
    return valor