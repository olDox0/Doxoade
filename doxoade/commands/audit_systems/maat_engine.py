# -*- coding: utf-8 -*-
# doxoade/commands/audit_systems/maat_engine.py
"""
MA'AT Engine - O Julgamento do Código v1.0.
Orquestrador central de anti-regressão e conformidade PASC/OSL.
"""
import os
from doxoade.tools.doxcolors import Fore, Style
from .maat_weights import WeightGuard
from .maat_parity import ParityGuard
class MaatEngine:
    def __init__(self, root_path):
        self.root = root_path
        self.findings = []
        self.score = 100
        self.guards = [WeightGuard(self.root), ParityGuard(self.root)]
    def run_full_audit(self, target_files: list):
        from ...dnm import DNM
        dnm = DNM(self.root)
        
        sane_files = []
        for f in target_files:
            abs_f = os.path.abspath(f).replace('\\', '/')
            # PASC 8.17: O Juiz ignora o que não é real ou está bloqueado
            if os.path.isfile(abs_f) and not dnm.is_ignored(abs_f):
                try:
                    with open(abs_f, 'rb') as _: pass
                    sane_files.append(abs_f)
                except (OSError, PermissionError):
                    continue
        
        if not sane_files: return True, []
        # UI delegada para método específico (Resolve Deepcheck)
        self._report_start(len(sane_files))
        
        for guard in self.guards:
            for f in guard.audit(sane_files):
                self.register_finding(f)
        
        return self.generate_verdict()
    def _report_start(self, count):
        print(f"{Fore.CYAN}⚖  [MA'AT] Auditando {count} arquivos de produção...{Style.RESET_ALL}")
    def register_finding(self, finding):
        self.findings.append(finding)
        penalties = {'CRITICAL': 30, 'ERROR': 15, 'WARNING': 5}
        self.score -= penalties.get(finding.get('severity', 'WARNING'), 2)
    def generate_verdict(self):
        is_stable = self.score >= 80 and not any(f.get('severity') == 'CRITICAL' for f in self.findings)
        print(f"\n{Fore.WHITE}Resultado do Julgamento: {self._get_score_color()}{self.score}/100{Style.RESET_ALL}")
        if not is_stable:
            print(f"{Fore.RED}{Style.BRIGHT}✘ [VEREDITO] CAOS DETECTADO. Regressões impedem o avanço.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}{Style.BRIGHT}✔ [VEREDITO] EQUILÍBRIO MANTIDO.{Style.RESET_ALL}")
        return is_stable, self.findings
    def _get_score_color(self):
        if self.score >= 90: return Fore.GREEN
        if self.score >= 70: return Fore.YELLOW
        return Fore.RED