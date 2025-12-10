import os
import sys
import re  # [DEADCODE] Import não usado
import hashlib
import subprocess

# [STYLE] Falta docstring do módulo aqui

def funcao_caotica():
    # [STYLE] Falta docstring da função
    
    # [QA] Lembretes
    # TODO: Refatorar esta função inteira
    # FIXME: Corrigir vazamento de memória
    # HACK: Gambiarra temporária
    
    # [DEADCODE] Redefinição inútil
    x = 10
    x = 20
    
    # [STYLE] F-string sem placeholder
    print(f"Olá mundo")
    
    # [RUNTIME-RISK] Nome indefinido (Abdução deve sugerir 'import json')
    dados = json.dumps({"a": 1})
    
    # [SECURITY] Eval (Execução de código arbitrário)
    eval("print('perigo')")
    
    # [SECURITY] Senha Hardcoded
    password = "secret_123"
    
    # [SECURITY] Hash fraco (MD5)
    h = hashlib.md5(b"texto")
    
    # [SECURITY] Shell Injection
    cmd = "ls -la"
    subprocess.run(cmd, shell=True)
    
    # [MPoT] Uso de Global
    global estado_global
    estado_global = 1
    
    return x

def funcao_gigante_mpt_regra_4():
    """Esta função testa a regra de coesão (>60 linhas)."""
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
    print("Linha 62 - Estouro do limite")
    return True