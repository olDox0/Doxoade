# doxoade/doxoade/diagnostic/debug_op_sentry.py
import os
import sys
import subprocess
# [DOX-UNUSED] import shutil
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

def check_infra():
    print(f"{Fore.CYAN}{Style.BRIGHT}🔍 [ DEBUG OPERATIONAL SENTRY ]{Style.RESET_ALL}")
    
    # 1. Teste de Raiz e Espaços (The Root Plague)
    root = os.getcwd()
    print("\n1. Verificando Caminho do Projeto:")
    print(f"   Path: {root}")
    if " " in root:
        print(f"   {Fore.YELLOW}⚠️  ALERTA: Espaços detectados. Pode causar falhas no Windows.{Style.RESET_ALL}")
    else:
        print(f"   {Fore.GREEN}✅ Caminho limpo.{Style.RESET_ALL}")

    # 2. Verificação de Integridade dos Wrappers
    print("\n2. Integridade dos Subsistemas:")
    probes_dir = Path(__file__).resolve().parents[1] / "probes"
    subsystems = ['command_wrapper.py', 'flow_runner.py', 'debug_probe.py']
    
    for sub in subsystems:
        p = probes_dir / sub
        status = f"{Fore.GREEN}OK" if p.exists() else f"{Fore.RED}FALTANDO"
        print(f"   • {sub:<20}: {status}{Style.RESET_ALL}")

    # 3. Teste de Invocação (Canary Test)
    print("\n3. Teste de Permissão de Subprocesso (WinError 5 Check):")
    try:
        # Tenta rodar um python -c simples para ver se o SO bloqueia
        res = subprocess.run([sys.executable, "-c", "print('canary_ok')"], 
                            capture_output=True, text=True, timeout=5)
        if "canary_ok" in res.stdout:
            print(f"   {Fore.GREEN}✅ Subprocesso autorizado pelo Sistema Operacional.{Style.RESET_ALL}")
        else:
            print(f"   {Fore.RED}❌ Falha na captura de saída.{Style.RESET_ALL}")
    except Exception as e:
        print(f"   {Fore.RED}❌ ERRO DE PERMISSÃO: {e}{Style.RESET_ALL}")

    # 4. Verificação de Escopo de Ambiente
    print("\n4. Sincronia de VENV:")
    venv = os.environ.get('VIRTUAL_ENV', 'NÃO DETECTADO')
    print(f"   VENV Ativo: {venv}")
    if venv == 'NÃO DETECTADO' or Path(sys.prefix).resolve() != Path(venv).resolve():
        print(f"   {Fore.YELLOW}⚠️  AVISO: Venv pode estar dessincronizado com o Interpretador.{Style.RESET_ALL}")
    else:
        print(f"   {Fore.GREEN}✅ Ambiente isolado e consistente.{Style.RESET_ALL}")

def check_syntax_integrity():
    print("\n5. Verificando Integridade de Código (Syntax Check):")
    core_files = [
        'doxoade/tools/doxcolors.py',
        'doxoade/tools/error_info.py',
        'doxoade/cli.py',
        'doxoade/rescue.py'
    ]
    
    for rel_path in core_files:
        abs_p = Path(os.getcwd()) / rel_path
        if not abs_p.exists(): continue
        
        try:
            with open(abs_p, 'r', encoding='utf-8', errors='ignore') as f:
                compile(f.read(), rel_path, 'exec')
            print(f"   • {rel_path:<25}: {Fore.GREEN}INTEGRO{Style.RESET_ALL}")
        except SyntaxError as e:
            print(f"   • {rel_path:<25}: {Fore.RED}CORROMPIDO (L{e.lineno}){Style.RESET_ALL}")
            print(f"     {Fore.RED}>> Erro: {e.msg}{Style.RESET_ALL}")

if __name__ == "__main__":
    check_infra()
    check_syntax_integrity()