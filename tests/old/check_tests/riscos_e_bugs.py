import os
import modulo_que_nao_existe  # Import Probe deve pegar
import sys

def perigo(lista=[]):  # Hunter: Argumento mutável
    # Static: Variável não usada
    x = 10
    
    # Hunter: Except genérico
    try:
        eval("print('Ola')") # Hunter: Eval (Segurança)
    except:
        pass

    # Static: Variável indefinida (Abdução deve sugerir import)
    print(math.pi)