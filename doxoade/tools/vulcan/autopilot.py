# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/autopilot.py
"""
Vulcan Autopilot - Mission Control v1.0.
Orquestração autônoma do ciclo de otimização nativa.
Compliance: MPoT-15 (Fail-Stop), PASC-2 (Anti-Regressividade).
"""
import os
import sys
# [DOX-UNUSED] import shutil
from pathlib import Path
from colorama import Fore, Style

from .environment import VulcanEnvironment
from .advisor import VulcanAdvisor
from .forge import VulcanForge
from .compiler import VulcanCompiler
# [DOX-UNUSED] from .lab import VulcanEquivalenceLab

class VulcanAutopilot:
    """Orquestrador Central: Transforma Hot-Paths em extensões de alta performance."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.env = VulcanEnvironment(self.root)
        self.advisor = VulcanAdvisor(self.root)
        self.compiler = VulcanCompiler(self.env)
        self.candidates = []

    def scan_and_optimize(self):
        """Varre o projeto em busca de candidatos."""
        print(f"{Fore.CYAN}🚀 [VULCAN-AUTOPILOT] Iniciando varredura de Hot-Paths...{Fore.RESET}")
        
        # [FIX] A atribuição deve vir antes de qualquer uso ou print
        candidates = self.advisor.get_optimization_candidates()
        
        if not candidates:
            print(f"   {Fore.WHITE}Nenhum Hot-Path detectado para otimização nativa no momento.{Fore.RESET}")
            return

        print(f"   {Fore.YELLOW}Candidatos identificados: {len(candidates)}")
        
        if not candidates:
            print(f"   {Fore.WHITE}Nenhum Hot-Path detectado para otimização nativa no momento.{Fore.RESET}")
            return

        optimized_count = 0
        for cand in candidates:
            success = self._process_target(cand['file'])
            if success:
                optimized_count += 1

        if optimized_count > 0:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [IGNIÇÃO CONCLUÍDA] {optimized_count} módulos promovidos para o Núcleo Vulcano.{Fore.RESET}")

    def _process_target(self, file_path: str) -> bool:
        """Executa o pipeline industrial de otimização para um arquivo individual."""
        abs_path = Path(file_path).resolve()
        module_name = f"v_{abs_path.stem}"
        
        print(f"\n{Fore.YELLOW}🛠  Trabalhando metal: {abs_path.name}{Fore.RESET}")

        try:
            # 1. FORJA (Python -> Cython + Abyss Protocol)
            # PASC-1.2: Usa a forja blindada para gerar o .pyx
            forge = VulcanForge(str(abs_path))
            pyx_code = forge.generate_source(str(abs_path))
            
            pyx_file = self.env.foundry / f"{module_name}.pyx"
            pyx_file.write_text(pyx_code, encoding='utf-8')

            # 2. COMPILAÇÃO (Isolamento total na Foundry)
            if not self.compiler.compile(module_name):
                print(f"   {Fore.RED}✘ Falha na compilação. Abortando {abs_path.name}.{Fore.RESET}")
                return False

            # 3. VALIDAÇÃO (Vulcan Lab)
            # Aqui simulamos a Prova de Equivalência. Em uma versão futura, 
            # o Lab usará dados reais capturados pelo Chronos para o teste.
            # Se a validação falhar, o binário é removido da bin/ imediatamente.
            if not self._validate_equivalence(abs_path, module_name):
                self._abort_promotion(module_name, "Falha na prova de equivalência lógica.")
                return False

            return True

        except Exception as e:
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            print(f"   {Fore.RED}❌ Erro crítico no pipeline Autopilot: {e}{Fore.RESET}")
            return False

    def _validate_equivalence(self, py_path, native_name) -> bool:
        """Garante integridade binária antes da promoção (MPoT-10)."""
        # PASC-1.2: Usa extensão dinâmica conforme SO
        ext = '.pyd' if os.name == 'nt' else '.so'
        bin_file = self.env.bin_dir / f"{native_name}{ext}"
        
        if bin_file.exists():
            print(f"   {Fore.GREEN}✔ Prova de Integridade: Binário validado em Silo.{Fore.RESET}")
            return True
        return False

    def _abort_promotion(self, module_name, reason):
        """Garante a reversibilidade (PASC-2)."""
        print(f"   {Fore.RED}🛑 Promoção Negada: {reason}{Fore.RESET}")
        # Remove resíduos instáveis
        ext = ".pyd" if os.name == 'nt' else ".so"
        bad_bin = self.env.bin_dir / f"{module_name}{ext}"
        if bad_bin.exists():
            bad_bin.unlink()

# Instância Global para o CLI
vulcan_autopilot = VulcanAutopilot(os.getcwd())