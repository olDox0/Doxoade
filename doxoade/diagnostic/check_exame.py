# doxoade/doxoade/diagnostic/check_exame.py
import os
import sys

def funcao_complexa(a):
    """Gera aviso de complexidade se houver muitos desvios."""
    if a > 1:
        if a > 2:
            if a > 3:
                for i in range(a):
                    while True:
                        break
    return a

def risco_seguranca():
    eval("print('vulneravel')")

def erro_runtime():
    return variavel_inexistente + 10

def argumento_mutavel(lista=[]):
    return lista

def teste_contrato(valor):
    if valor is None:
        raise ValueError('Contrato: valor não pode ser nulo')
    return valor