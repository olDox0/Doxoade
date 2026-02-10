# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/check_filters.py 
"""
Crivo de Qualidade e Injeção de Dívida Técnica (PASC 8.5 / MPoT-3).
Responsável por filtrar silenciadores (# noqa) e injetar lembretes.
"""
import os
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

def apply_filters(state: 'CheckState', **kwargs):
    """Crivo Industrial de Categorias e Silenciadores (PASC 8.5)."""
    raw = state.findings
    state.findings = []
    processed_files = set()
    
    # 1. Mapeamento de Filtros
    exclude_cats = {c.upper() for c in (kwargs.get('exclude') or [])}
    only_cat = kwargs.get('only').upper() if kwargs.get('only') else None
    
    for f in raw:
        cat = f.get('category', 'STYLE').upper()
        
        # --- FILTRAGEM DE CATEGORIA (Fix: -x e -o) ---
        if only_cat and cat != only_cat: continue
        if cat in exclude_cats: continue

        # --- SILENCIADOR ALB ---
        if cat == 'SYSTEM':
            # Se for ALB_REDUCED, move para a lista de omitidos e NÃO registra no findings
            if f.get('message') == 'ALB_REDUCED':
                state.alb_files.append(f.get('file'))
            continue

        state.register_finding(f)
        
        # Injeção de TODOs
        abs_path = os.path.abspath(f.get('file'))
        if abs_path not in processed_files and 'QA-REMINDER' not in exclude_cats:
            lines = ufs.get_lines(abs_path)
            _inject_qa_reminders(state, lines, abs_path)
            processed_files.add(abs_path)

    # 2. Sincronização de Sumário (Fix: Rodapé atualizado)
    state.sync_summary()

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