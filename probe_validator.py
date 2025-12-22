import os
import sys
import json
import subprocess
import shutil
from colorama import Fore, Style, init

init(autoreset=True)

TEMP_DIR = "temp_probe_test"
DOXOADE_BIN = [sys.executable, "-m", "doxoade", "check", TEMP_DIR, "--format=json", "--no-cache", "--continue-on-error"]

# Cenários de Teste (Cirurgia)
SCENARIOS = [
    {
        "name": "Sintaxe Quebrada",
        "file": "bad_syntax.py",
        "content": "def foo()\n    pass", # Falta :
        "expect_category": "SYNTAX",
        "must_find": True
    },
    {
        "name": "Risco de Segurança (Eval)",
        "file": "security_risk.py",
        "content": "x = eval('input()')",
        "expect_category": "SECURITY",
        "must_find": True
    },
    {
        "name": "Risco de Runtime (NameError)",
        "file": "runtime_risk.py",
        "content": "def foo():\n    print(variavel_inexistente)",
        "expect_category": "RUNTIME-RISK", # Pyflakes 'undefined name'
        "must_find": True
    },
    {
        "name": "Importação Fantasma",
        "file": "bad_import.py",
        "content": "import modulo_que_nao_existe_123",
        "expect_category": "DEPENDENCY", # Import Probe (se configurado como crítico) ou DEADCODE se só pyflakes pegar
        "expect_alternative": "DEADCODE",
        "must_find": True
    },
    {
        "name": "Estilo (Função Longa)",
        "file": "bad_style.py",
        "content": "def long_func():\n" + "\n".join([f"    a={i}" for i in range(100)]),
        "expect_category": "COMPLEXITY", # Ou STYLE
        "must_find": True
    }
]

def setup():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    for sc in SCENARIOS:
        with open(os.path.join(TEMP_DIR, sc['file']), 'w', encoding='utf-8') as f:
            f.write(sc['content'])

def run_test():
    print(Fore.CYAN + "--- [PROBE VALIDATOR] Iniciando Teste Cirúrgico ---")
    
    # Executa o Doxoade Check no diretório tóxico
    result = subprocess.run(DOXOADE_BIN, capture_output=True, text=True, encoding='utf-8')
    
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(Fore.RED + "[FATAL] O Doxoade não retornou JSON válido.")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    all_findings = []
    if 'file_reports' in data:
        for report in data['file_reports'].values():
            all_findings.extend(report.get('static_analysis', {}).get('findings', []))
    
    # Se a estrutura for plana (dependendo da versão do seu check.py)
    if 'findings' in data:
        all_findings.extend(data['findings'])

    success_count = 0
    
    print(f"Encontrados {len(all_findings)} problemas no total.\n")

    for sc in SCENARIOS:
        found = False
        detected_cats = []
        
        target_file = sc['file']
        
        # Procura se o arquivo gerou o erro esperado
        for finding in all_findings:
            # Normaliza caminhos para comparação
            f_path = finding.get('file', '').replace('\\', '/')
            if target_file in f_path:
                cat = finding.get('category', 'UNKNOWN')
                detected_cats.append(cat)
                
                expected = sc.get('expect_category')
                alt = sc.get('expect_alternative')
                
                if cat == expected or cat == alt:
                    found = True
        
        if found:
            print(f"{Fore.GREEN}[PASS] {sc['name']:<30} -> Detectado como {detected_cats}")
            success_count += 1
        else:
            print(f"{Fore.RED}[FAIL] {sc['name']:<30} -> NÃO DETECTADO!")
            print(f"       Esperado: {sc['expect_category']}")
            print(f"       Encontrado: {detected_cats}")

    print("-" * 50)
    if success_count == len(SCENARIOS):
        print(Fore.GREEN + Style.BRIGHT + "SISTEMA OPERACIONAL: Todas as sondas estão ativas.")
        return True
    else:
        print(Fore.RED + Style.BRIGHT + f"FALHA SISTÊMICA: Apenas {success_count}/{len(SCENARIOS)} sondas responderam.")
        return False

def cleanup():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

if __name__ == "__main__":
    setup()
    try:
        success = run_test()
    finally:
        cleanup()
    
    sys.exit(0 if success else 1)