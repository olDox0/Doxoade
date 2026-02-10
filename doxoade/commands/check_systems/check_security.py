# -*- coding: utf-8 -*-
"""
Security Bridge - v81.7 Gold.
Refatorado para Expert-Split para eliminar hibridismo UI/SYS.
"""
import os
from click import progressbar, echo
from colorama import Fore
from .check_state import CheckState
from ..security_utils import get_tool_path, SEVERITY_MAP, batch_list

def analyze_security(state: CheckState):
    """Orquestrador da Auditoria de Segurança (CC: 2)."""
    # 1. Auditoria de Código (SAST)
    _audit_sast_integration(state)
    
    # 2. Auditoria de Dependências (SCA)
    _audit_sca_integration(state)

def _audit_sast_integration(state: CheckState):
    """Especialista em processamento Bandit com ProgressBar."""
    from ..security import _run_bandit_engine
    
    if not get_tool_path('bandit') or not state.target_files:
        return

    batches = list(batch_list(state.target_files, 10))
    with progressbar(batches, label='Escudo Aegis (SAST)') as bar:
        for batch in bar:
            results = _run_bandit_engine(batch, set())
            for res in results:
                if _is_security_relevant(res, state.root):
                    state.register_finding({
                        'severity': res['severity'],
                        'category': 'SECURITY',
                        'message': f"[{res['tool']}] {res['message']}",
                        'file': res['file'],
                        'line': res['line'],
                        'details': f"Fragmento: {res.get('code', 'N/A')}"
                    })

def _audit_sca_integration(state: CheckState):
    """Especialista em processamento Safety."""
    from ..security import _run_safety_engine
    
    req_path = os.path.join(state.root, "requirements.txt")
    if os.path.exists(req_path):
        echo(Fore.MAGENTA + "   > Analisando dependências (SCA)...")
        sca_results = _run_safety_engine(state.root, None)
        for res in (sca_results or []):
            state.register_finding(res)

def _is_security_relevant(res: dict, root: str) -> bool:
    """Filtro de Relevância Aegis (Silencia ruído de infra no Core)."""
    msg = res['message'].lower()
    # Se for o próprio Doxoade, ignoramos avisos de subprocess/exec (são ferramentas do Core)
    if "doxoade" in root.lower():
        if any(x in msg for x in ["subprocess", "use of exec"]):
            return False
    return SEVERITY_MAP.get(res.get('severity', 'LOW'), 1) >= 2