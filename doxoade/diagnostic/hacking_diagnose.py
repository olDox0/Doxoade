# doxoade/diagnostic/hacking_diagnose.py
"""
Diagnostic: Security Suite Integrity Test.
Validates Aegis Sandbox and Hashing Consistency.
"""
import os
from colorama import Fore, Style
from ..tools.security_utils import calculate_integrity_hash, restricted_safe_exec
from pathlib import Path

def run_security_diagnose():
    print(f"{Fore.CYAN}--- [DIAGNOSTIC] Security & Hacking Integrity ---{Style.RESET_ALL}")
    
    # TESTE 1: Integridade do Hasher
    print(f"\n1. Testing Hashing Consistency...")
    core_path = Path(__file__).parent.parent
    hash_1 = calculate_integrity_hash(core_path)
    hash_2 = calculate_integrity_hash(core_path)
    
    if hash_1 == hash_2:
        print(f"   {Fore.GREEN}✔ Hash Determinism: OK ({hash_1[:8]})")
    else:
        print(f"   {Fore.RED}✘ Hash Determinism: FAILED (Non-deterministic output)")

    # TESTE 2: Efetividade do Sandbox Aegis
    print(f"\n2. Testing Aegis Sandbox (Attack Simulation)...")
    
    # Payload que tenta importar o módulo OS (Proibido pela Regra 8.3)
    malicious_code = "import os; print(os.getcwd())"
    
    try:
        restricted_safe_exec(malicious_code)
        print(f"   {Fore.RED}✘ Sandbox Breach: FAILED (Malicious import allowed!){Style.RESET_ALL}")
    except RuntimeError as e:
        if "Sandbox Breach" in str(e) or "imports are forbidden" in str(e).lower():
            print(f"   {Fore.GREEN}✔ Sandbox Defense: OK (Blocked malicious import)")
            print(f"     {Style.DIM}Reason: {e}{Style.RESET_ALL}")
        else:
            print(f"   {Fore.YELLOW}⚠ Sandbox Warning: Unexpected Error ({e})")

    # TESTE 3: Bloqueio de Introspecção
    print(f"\n3. Testing Introspection Block (dunder access)...")
    dunder_code = "x = [].__class__.__base__"
    try:
        restricted_safe_exec(dunder_code)
        print(f"   {Fore.RED}✘ Introspection Defense: FAILED (Dunder access allowed!)")
    except RuntimeError:
        print(f"   {Fore.GREEN}✔ Introspection Defense: OK (Blocked __ access)")

    print(f"\n{Fore.CYAN}--- Security Diagnosis Complete ---{Style.RESET_ALL}")

if __name__ == "__main__":
    run_security_diagnose()