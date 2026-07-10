# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/test_hbc6_builder.py
"""
Script de Prova de Conceito (PoC) para o HBC6 Builder.
Pega os N-grams reais do seu projeto e simula a cirurgia de bytecode.
"""
import sys
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.hermes_opcode_builder import HBC6Builder

def main():
    project_root = Path(__file__).resolve().parents[3]
    
    # 1. O DICIONÁRIO GLOBAL (Os Top N-grams que o Lab caçou)
    # Estes são os "DNA" repetitivos do seu projeto (ex: Setup de Imports)
    GLOBAL_NGRAMS = {
        'hash_import_1': ['LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'],
        'hash_import_2': ['LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME', 'LOAD_CONST'],
        'hash_import_3': ['IMPORT_NAME', 'STORE_NAME', 'LOAD_CONST', 'LOAD_CONST'],
        'hash_try_1': ['PUSH_EXC_INFO', 'WITH_EXCEPT_START', 'JUMP', 'RERAISE'],
        'hash_call_1': ['LOAD_FAST', 'LOAD_ATTR', 'CALL', 'POP_TOP'],
    }

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🏗️  [HBC6 BUILDER] Iniciando Cirurgia de Bytecode...{Style.RESET_ALL}")
    print(f"  Dicionário Global: {len(GLOBAL_NGRAMS)} Macros Atômicas carregadas.")
    
    builder = HBC6Builder(str(project_root), GLOBAL_NGRAMS)
    
    # 2. ALVO: A pasta mais densa do seu projeto (Vulcan)
    target_dir = project_root / 'doxoade' / 'tools' / 'vulcan'
    py_files = list(target_dir.rglob('*.py'))
    
    print(f"  Varrendo {len(py_files)} arquivos em {target_dir.name}...\n")
    
    # 3. EXECUTA A CIRURGIA (Simulação)
    for py_file in py_files:
        if '.doxoade' in str(py_file) or 'venv' in str(py_file):
            continue
        result = builder.analyze_file(py_file)
        if 'error' in result:
            continue
            
        if result['saved_bytes'] > 0:
            print(f"  {Fore.GREEN}✔{Style.RESET_ALL} {py_file.name:<30} | "
                  f"Economia: {result['saved_bytes']:>4}B | "
                  f"Macros: {result['macros_found']:<3} | "
                  f"HRT: {result['hrt_entries']:<3}")
            if result['hrt_sample']:
                print(f"    {Fore.CYAN}↳ HRT Sample:{Style.RESET_ALL} Jump no offset {result['hrt_sample'][0]['jump_offset']} precisa de Delta {result['hrt_sample'][0]['delta']}")

    # 4. RELATÓRIO FINAL
    builder.print_report()

if __name__ == '__main__':
    main()