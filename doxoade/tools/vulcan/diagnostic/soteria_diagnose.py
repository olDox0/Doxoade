# -*- coding: utf-8 -*-
import os, sys, re, json, difflib
from pathlib import Path
from datetime import datetime

ARTIFACT_DIR = Path(".doxoade/artifacts/audit_rescue")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(".doxoade/logs/soteria_rescue.log")

class NexusAudit:
    def __init__(self):
        self.reset = "\033[0m"; self.red = "\033[1;31m"; self.grn = "\033[1;32m"; self.ylw = "\033[1;33m"

    def log(self, status, msg, evidence=None):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{status}] {msg}\n")
            if evidence: f.write(f"--- EVIDÊNCIA ---\n{evidence}\n-----------------\n")
        
        color = self.grn if status == "OK" else self.red if status == "FAIL" else self.ylw
        print(f"{color}[{status}]{self.reset} {msg}")

    def audit_scribe(self):
        print(f"\n{self.ylw}🧪 [FASE 1] Auditoria de Vacinação (Scribe){self.reset}")
        from doxoade.tools.vulcan.diagnostic.soteria.scribe import SoteriaScribe
        scribe = SoteriaScribe()
        
        # Amostra de código que deveria disparar marcos
        test_code = "void test_func() {\n    int *ptr = malloc(100);\n    *ptr = 10;\n    exit(1);\n}"
        vacinado = scribe.instrument_code(test_code, "audit_sample.c")
        
        # Artefato 1: O código gerado para inspeção manual
        (ARTIFACT_DIR / "audit_sample_vacinado.c").write_text(vacinado)
        
        # Teste de integridade
        v_count = vacinado.count("SOTERIA_ENTER")
        m_count = vacinado.count("soteria_mark")
        
        if m_count > 0:
            self.log("OK", f"Marcos injetados: {m_count}. Artefato salvo em {ARTIFACT_DIR}/audit_sample_vacinado.c")
        else:
            diff = "".join(difflib.unified_diff(test_code.splitlines(1), vacinado.splitlines(1)))
            self.log("FAIL", "Scribe ignorou as linhas de risco.", f"CÓDIGO ORIGINAL:\n{test_code}\n\nDIFF GERADO:\n{diff}")
            print(f"      {self.red}DEBUG: Regex de Risco usada: {scribe.risk_regex.pattern}{self.reset}")

    def audit_lazarus_path(self):
        print(f"\n{self.ylw}🧪 [FASE 2] Auditoria de Triangulação (Rescue){self.reset}")
        from doxoade.rescue import analyze_crash
        
        # Teste com caminho complexo do Windows (Onde o bug "A" costuma atacar)
        path_sujo = "C:\\Users\\Doxo\\Project\\src\\main.c:120"
        mock_log = f"@SOTERIA_BEGIN@\nTAG_RASTRO_LOC: {path_sujo}\n@SOTERIA_END@"
        
        dossier = analyze_crash(mock_log, exit_code=1)
        
        # Artefato 2: O Dossiê gerado
        (ARTIFACT_DIR / "mock_dossier.json").write_text(json.dumps(dossier, indent=2))

        if dossier['file'] == "main.c" or "src/main.c" in dossier['file']:
            self.log("OK", f"Caminho Windows resolvido: {dossier['file']} L{dossier['line']}")
        else:
            self.log("FAIL", f"Corrupção de caminho detectada.", f"Entrada: {path_sujo}\nResultado no Dossiê: {dossier['file']}")

    def audit_oom_metrics(self):
        print(f"\n{self.ylw}🧪 [FASE 3] Auditoria de Métricas (OOM TNSE){self.reset}")
        from doxoade.rescue import analyze_crash
        
        # Simula o erro real que você teve no TNSE
        oom_log = "TAG_DETAIL: OOM: Pedido 1048576 bytes, restam 933104\n@NEXUS_END@"
        dossier = analyze_crash(oom_log, exit_code=1)
        
        if "115,472" in dossier['explanation'] or "115472" in dossier['explanation']:
            self.log("OK", "Cálculo de déficit de Arena validado.")
        else:
            self.log("FAIL", "Falha ao extrair/calcular métricas de OOM.", f"Explicação gerada: {dossier['explanation']}")


if __name__ == "__main__":
    audit = NexusAudit()
    audit.audit_scribe()
    audit.audit_lazarus_path()
    audit.audit_oom_metrics()