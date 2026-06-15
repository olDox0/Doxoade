# doxoade/diagnostic/shadow_audit.py
import sys
import os
import ast
import json
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

def audit_the_watchmen():
    print(f"{Fore.CYAN}{Style.BRIGHT}🔬 [SHADOW AUDIT] Investigando o Motor de Rastro...{Style.RESET_ALL}")
    
    # 1. Verificar MetaPath
    print(f"\n1. Localizando Finder no MetaPath:")
    finder = next((f for f in sys.meta_path if 'ShadowFinder' in str(type(f))), None)
    if finder:
        print(f"   {Fore.GREEN}✔ ShadowFinder está ativo no índice {sys.meta_path.index(finder)}.{Style.RESET_ALL}")
    else:
        print(f"   {Fore.RED}✘ ShadowFinder NÃO ENCONTRADO no sistema de importação.{Style.RESET_ALL}")

    # 2. Teste de Transpilação (A Cirurgia AST)
    print(f"\n2. Testando Scribe (Vacinador):")
    try:
        from doxoade.tools.aegis.shadow_scribe import NexusShadowScribe
        test_code = "def target(): return 1 + 1"
        tree = ast.parse(test_code)
        scribe = NexusShadowScribe("audit_test.py")
        vax_tree = scribe.visit(tree)
        
        # Verifica se o Scribe injetou o chief_heartbeat
        vax_source = ast.unparse(vax_tree)
        if "chief_heartbeat" in vax_source:
            print(f"   {Fore.GREEN}✔ Scribe injetando telemetria com sucesso.{Style.RESET_ALL}")
            if "audit_test.py" in vax_source:
                print(f"   {Fore.GREEN}✔ Nome do arquivo preservado na injeção.{Style.RESET_ALL}")
            else:
                print(f"   {Fore.YELLOW}⚠ ALERTA: Nome do arquivo omitido na injeção (Causa do <string>).{Style.RESET_ALL}")
        else:
            print(f"   {Fore.RED}✘ Scribe falhou: rastro não detectado no código transformado.{Style.RESET_ALL}")
    except Exception as e:
        print(f"   {Fore.RED}✘ Erro ao invocar Scribe: {e}{Style.RESET_ALL}")

    # 3. Teste de Identidade de Compilação
    print(f"\n3. Validando Identidade de Objeto (Code Object):")
    try:
        # O compile deve levar o filename para que o rastro seja rastreável
        filename = "diagnose_test.py"
        code_obj = compile(ast.parse("pass"), filename, 'exec')
        if code_obj.co_filename == filename:
            print(f"   {Fore.GREEN}✔ O compilador Python aceita a identidade do arquivo.{Style.RESET_ALL}")
        else:
            print(f"   {Fore.RED}✘ O compilador forçou a identidade para {code_obj.co_filename}.{Style.RESET_ALL}")
    except Exception as e:
        print(f"   {Fore.RED}✘ Falha no teste de compilação: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    audit_the_watchmen()