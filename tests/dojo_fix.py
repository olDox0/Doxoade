import os
import sys
import re  # Não usado

def teste_dojo():
    x = 10
    x = 20  # Redefinição inútil
    
    print("Ola mundo")  # f-string inútil
    
    # Teste de Abdução: json não está importado
    data = json.dumps({"a": 1})
    
    local_unused = "ninguem me usa"
    
    return True