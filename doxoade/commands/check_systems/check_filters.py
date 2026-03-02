# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/check_filters.py 
"""
Crivo de Qualidade e Injeção de Dívida Técnica (PASC 8.5 / MPoT-3).
Responsável por filtrar silenciadores (# noqa) e injetar lembretes.
"""
# [DOX-UNUSED] import os
from typing import List, Dict, Any, Set
from ...tools.streamer import ufs
from ...shared_tools import _get_code_snippet
from .check_state import CheckState
# Configurações de Crivo
SILENCERS: Set[str] = {'noqa', 'ignore', 'skipline', 'suppress', 'disable'}
FACADE_FILES: Set[str] = {'shared_tools.py', '__init__.py', 'cli.py'}
QA_TAGS: Dict[str, str] = {
    'TODO': 'INFO', 'FIXME': 'WARNING', 'BUG': 'ERROR', 
    'HACK': 'WARNING', 'ADTI': 'CRITICAL'
}
def apply_filters(state: 'CheckState', *args, **kwargs):
    if state is None or not hasattr(state, "findings"):
        return
    """Crivo Industrial Nexus v100.8 (Aegis Shield)."""
    raw_findings = state.findings
    state.findings = []

    for f in raw_findings:
        file_path = f.get('file', '').replace('\\', '/')
        line_num = f.get('line', 0)
        msg = f.get('message', '').lower()
        
        # 1. EXCEÇÃO DE INFRAESTRUTURA: O core precisa de exec/subprocess
        if "security_utils.py" in file_path and ("exec" in msg or "eval" in msg):
            continue
            
        # 2. SILENCIADOR # noqa: Verifica se a linha original tem a tag
        if line_num > 0:
            lines = ufs.get_lines(file_path)
            if lines and line_num <= len(lines):
                if "# noqa" in lines[line_num - 1].lower():
                    continue
        # 3. FILTRO DE CATEGORIA (kwargs)
        exclude_cats = {c.upper() for c in (kwargs.get('exclude') or [])}
        if f.get('category', 'STYLE').upper() in exclude_cats:
            continue
        state.register_finding(f)
    
    state.sync_summary()
def _should_silence(finding: dict, exclude_cats: set | None = None) -> bool:
    exclude_cats = exclude_cats or set()
    """Centraliza a lógica de silenciamento técnico (MPoT-1)."""
    msg = finding.get('message', '').lower()
    file_path = finding.get('file', '').replace('\\', '/')
    cat = finding.get('category', 'STYLE').upper()
    if cat in exclude_cats: return True
    # REGRA 1: Silenciar 'exec' em ferramentas de infraestrutura
    if "security_utils.py" in file_path and "exec" in msg:
        return True
    # REGRA 2: Silenciar ruído de injeção Vulcan no venv_up
    if "venv_up.py" in file_path and "fore" in msg:
        return True
    # REGRA 3: Silenciar avisos de complexidade em arquivos de Terceiros/Docs
    if any(x in file_path for x in ["foundry/", "docs/", "tests/"]):
        if cat == "COMPLEXITY": return True
    return False
def _has_silencer(line_content: str) -> bool:
    """Detecta tags de supressão de erro."""
    if '#' not in line_content: return False
    comment = line_content.split('#', 1)[1].strip().lower()
    return any(tag in comment for tag in SILENCERS)
def _is_facade_noise(finding: Dict[str, Any], filename: str) -> bool:
    """Identifica falsos positivos em arquivos de roteamento/fachada."""
    if filename not in FACADE_FILES: return False
    msg = finding.get('message', '').lower()
    cat = finding.get('category', '').upper()
    return 'unused' in msg or 'redefinition' in msg or cat == 'DEADCODE'
def _inject_qa_reminders(state: 'CheckState', lines: List[str], file_path: str):
    """Extrai TODOs/ADTIs e os registra como achados de QA."""
    for i, line in enumerate(lines):
        if '#' not in line: continue
        
        comment_part = line.split('#', 1)[1].strip()
        tokens = comment_part.split()
        if not tokens: continue
            
        tag = tokens[0].upper().rstrip(':')
        if tag in QA_TAGS:
            # Proteção: Ignora se a linha contiver 'ignore-todo'
            if 'ignore-todo' in comment_part.lower(): continue
            state.register_finding({
                'severity': QA_TAGS[tag],
                'category': 'QA-REMINDER',
                'message': f"[{tag}] {comment_part[len(tag):].strip().lstrip(':').strip()}",
                'file': file_path,
                'line': i + 1,
                'snippet': _get_code_snippet(file_path, i + 1)
            })
            
def filter_and_inject_findings(findings: list, project_root: str) -> list:
    """Bridge de Compatibilidade: Conecta o motor legado à nova lógica (v84.2)."""
    from .check_state import CheckState
    # Cria um estado efêmero para processamento
    st = CheckState(root=project_root, target_path=project_root)
    st.findings = findings
    # Aciona a filtragem real
    apply_filters(st)
    return st.findings
    
def _calculate_incident_stats(findings: list) -> dict:
    from collections import defaultdict
    stats = defaultdict(lambda: defaultdict(int))
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat == 'SYSTEM': continue
        
        msg = f.get('message', '').lower()
        sub = "geral"
        # FIX: Agora a variável 'msg' é usada para as subcategorias
        if "f-string" in msg: sub = "f-string"
        elif "imported but unused" in msg: sub = "unused-import"
        elif "assigned to but never used" in msg: sub = "unused-variable"
        elif "except:" in msg or ("except" in msg and ":" in msg and "exception" not in msg): sub = "bare-except"
        
        stats[cat][sub] += 1
    return stats # FIX: 'stats' agora é retornado e usado