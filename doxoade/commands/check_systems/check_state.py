# doxoade/doxoade/commands/check_systems/check_state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class CheckState:
    root: str
    target_path: str
    target_files: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    alb_files: List[str] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=lambda: {'errors': 0, 'warnings': 0, 'critical': 0})
    is_full_power: bool = False
    clones_active: bool = False

    def register_finding(self, f: Dict[str, Any]):
        self.findings.append(f)
        sev = f.get('severity', 'WARNING').upper()
        if sev == 'CRITICAL':
            self.summary['critical'] += 1
        elif sev == 'ERROR':
            self.summary['errors'] += 1
        else:
            self.summary['warnings'] += 1

    def sync_summary(self):
        """Recalcula o sumário baseado nos achados ATUAIS (PASC 8.7)."""
        self.summary = {'errors': 0, 'warnings': 0, 'critical': 0}
        for f in self.findings:
            sev = f.get('severity', 'WARNING').upper()
            if sev == 'CRITICAL':
                self.summary['critical'] += 1
            elif sev == 'ERROR':
                self.summary['errors'] += 1
            else:
                self.summary['warnings'] += 1