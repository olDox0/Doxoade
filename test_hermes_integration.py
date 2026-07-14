# -*- coding: utf-8 -*-
# test_hermes_integration.py
"""
Teste de Integração: Hermes V2 em Produção
===========================================
Valida que o Hermes V2 está ativado no boot e coletando telemetria.
"""
import sys
import os
from pathlib import Path

def main():
    from doxoade.tools.doxcolors import Fore, Style
    
    print(f"\n{'═' * 70}")
    print(f"  🔬 HERMES V2 INTEGRATION TEST (PRODUÇÃO)")
    print(f"{'═' * 70}")
    
    # 1. Verifica se o Hermes V2 está ativado
    print(f"\n  {Fore.CYAN}▶ Verificando ativação do Hermes V2...{Style.RESET_ALL}")
    from doxoade.tools.hermes_systems.hermes_hook_v2 import _HERMES_FINDER_INSTANCE
    
    if _HERMES_FINDER_INSTANCE is None:
        print(f"  {Fore.RED}✘ Hermes V2 NÃO está ativado!{Style.RESET_ALL}")
        print(f"    Execute 'doxoade hermes build --all' primeiro.")
        return
    
    print(f"  {Fore.GREEN}✔ Hermes V2 está ativado.{Style.RESET_ALL}")
    print(f"    Módulos .hbc6 disponíveis: {len(_HERMES_FINDER_INSTANCE._module_cache)}")
    
    # 2. Importa alguns módulos críticos (serão interceptados pelo Hermes V2)
    print(f"\n  {Fore.CYAN}▶ Importando módulos críticos...{Style.RESET_ALL}")
    test_modules = [
        'doxoade.tools.filesystem',
        'doxoade.tools.doxcolors',
        'doxoade.tools.error_info',
    ]
    
    for module_name in test_modules:
        # Remove do cache para forçar o import via Hermes V2
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        print(f"    Importando {module_name}...")
        try:
            __import__(module_name)
            print(f"      {Fore.GREEN}✔{Style.RESET_ALL} {module_name} importado com sucesso.")
        except Exception as e:
            print(f"      {Fore.RED}✘{Style.RESET_ALL} Falha ao importar {module_name}: {e}")
    
    # 3. Imprime o relatório de telemetria
    print(f"\n  {Fore.CYAN}▶ Relatório de Telemetria:{Style.RESET_ALL}")
    from doxoade.tools.hermes_systems.hermes_hook_v2 import print_telemetry_report
    print_telemetry_report()
    
    print(f"\n{'═' * 70}\n")

if __name__ == '__main__':
    # Ativa o boot do Doxoade (que ativa o Hermes V2)
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))
    
    from doxoade.boot import ignite_background_systems
    ignite_background_systems(str(project_root))
    
    # Agora roda o teste
    main()