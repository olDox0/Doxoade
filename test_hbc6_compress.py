# -*- coding: utf-8 -*-
# test_hbc6_compress.py
"""
Prova de Conceito HBC6: Geração da Tabela de Patches (Patch-in-RAM).
"""
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.hermes_compress_hbc6 import HBC6Compressor

def main():
    project_root = Path(__file__).resolve().parent
    target_file = project_root / 'doxoade' / 'tools' / 'vulcan' / 'compiler.py'
    output_file = project_root / '.doxoade' / 'hermes' / 'build' / 'compiler.hbc6'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # O DICIONÁRIO GLOBAL (Os Top N-grams que o Lab caçou)
    GLOBAL_MACROS = {
        'hash_import_1': ['LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'],
        'hash_import_2': ['LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_FAST'],
        'hash_call_1': ['STORE_FAST', 'LOAD_FAST', 'LOAD_ATTR', 'CALL'],
        'hash_str_1': ['LOAD_CONST', 'BINARY_OP', 'LOAD_CONST', 'BINARY_OP'],
        'hash_fmt_1': ['FORMAT_VALUE', 'BUILD_STRING', 'CALL', 'POP_TOP'],
    }
    
    # Mapeia Hash -> Token ID (0 a 253)
    TOKEN_MAP = {h: i for i, h in enumerate(GLOBAL_MACROS.keys())}

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🏗️  [HBC6 COMPRESSOR] Iniciando Raio-X Cirúrgico (Patch-in-RAM)...{Style.RESET_ALL}")
    print(f"  Alvo: {target_file.name}")
    print(f"  Dicionário: {len(GLOBAL_MACROS)} Macros Atômicas.\n")

    compressor = HBC6Compressor(project_root, GLOBAL_MACROS, TOKEN_MAP)
#    compressor = HBC6Compressor(GLOBAL_MACROS, TOKEN_MAP)
    
    # EXECUTA A ANÁLISE E GERA O HBC6
    stats = compressor.compress_file(target_file, output_file)
    
    # RELATÓRIO DE ENGENHARIA
    print(f"{Fore.GREEN}{'═' * 70}")
    print(f"  📊 RELATÓRIO DE ENGENHARIA (HBC5 + HBC6 Unificado)")
    print(f"{'═' * 70}{Style.RESET_ALL}")
    print(f"  Arquivo Original (.py)   : {stats['original_bytes'] / 1024:.2f} KB")
    print(f"  Payload Marshal (Intacto): {stats['marshalled_bytes'] / 1024:.2f} KB")
    print(f"  Arquivo HBC6 Final       : {stats['hbc6_bytes'] / 1024:.2f} KB")
    print(f"  ──────────────────────────────────────────────────────────")
    print(f"  Code Objects Escaneados  : {Fore.CYAN}{stats['code_objects_scanned']}{Style.RESET_ALL}")
    print(f"  Patches Mapeados (HRT)   : {Fore.GREEN}{stats['patches_applied']}{Style.RESET_ALL} (Telemetria de Bytecode)")
    print(f"  Tokens de String (HBC5)  : {Fore.GREEN}{stats['tokens_applied']}{Style.RESET_ALL} (Compressão de co_consts)")
    print(f"  Arquivo de Saída         : {output_file}")
    print(f"{'═' * 70}\n")
    print(f"{Fore.YELLOW}💡 Próximo Passo:{Style.RESET_ALL} O Motor C (Mercury) fará o mmap do HBC6,")
    print(f"usará o Dicionário Global (HGD1) para expandir as strings tokenizadas,")
    print(f"e entregará um CodeObject 100% intacto e executável para o CPython.\n")

if __name__ == '__main__':
    main()