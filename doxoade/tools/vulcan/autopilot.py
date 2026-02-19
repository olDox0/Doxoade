# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/autopilot.py (v97.5 Platinum Batch)
import os
import sys
from pathlib import Path
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor # PASC 6.4

from .environment import VulcanEnvironment
from .advisor import VulcanAdvisor
from .forge import VulcanForge
from .compiler import VulcanCompiler

class VulcanAutopilot:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.env = VulcanEnvironment(self.root)
        self.advisor = VulcanAdvisor(self.root)
        self.compiler = VulcanCompiler(self.env)

    def scan_and_optimize(self):
        """Orquestração em Batch para alta performance de ignição."""
        print(f"{Fore.CYAN}🚀 [VULCAN-BATCH] Iniciando Varredura e Forja Paralela...{Fore.RESET}")
        
        candidates = self.advisor.get_optimization_candidates()
        if not candidates:
            print(f"   {Fore.WHITE}Nenhum Hot-Path detectado.{Fore.RESET}")
            return

        print(f"   {Fore.YELLOW}Candidatos identificados: {len(candidates)}")
        print(f"   {Fore.MAGENTA}🔥 Ativando múltiplos núcleos para compilação...{Fore.RESET}")

        # PASC 6.4: Limita a carga para não travar o PC do usuário (Cores - 1)
        max_workers = max(1, (os.cpu_count() or 2) - 1)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Dispara a forja para todos os candidatos em paralelo
            results = list(executor.map(lambda c: self._process_target(c['file']), candidates))

        optimized_count = sum(1 for r in results if r)
        if optimized_count > 0:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [IGNIÇÃO CONCLUÍDA] {optimized_count} módulos nativos prontos.{Fore.RESET}")

    def _process_target(self, file_path: str) -> bool:
        abs_path = Path(file_path).resolve()
        module_name = f"v_{abs_path.stem}"
        
        try:
            # Feedback visual imediato (MPoT-4)
            sys.stdout.write(f"\033[90m   [VULCAN:FORGE] {abs_path.name}...\033[0m\n")
            
            forge = VulcanForge(str(abs_path))
            pyx_code = forge.generate_source(str(abs_path))
            
            pyx_file = self.env.foundry / f"{module_name}.pyx"
            pyx_file.write_text(pyx_code, encoding='utf-8')

            if self.compiler.compile(module_name):
                # PROVA DE SUCESSO
                print(f"   \033[92m● {abs_path.name:<25} [METALIZADO]\033[0m")
                return True
            return False
        except Exception as e:
            print(f"   \033[31m✘ {abs_path.name:<25} [ERRO: {type(e).__name__}]\033[0m")
            return False
        return False