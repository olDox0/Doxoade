# doxoade/commands/check_filters.py (Versão Gold Corrigida)

import os
from typing import List, Dict, Any, Set
from ..shared_tools import _get_code_snippet

SILENCERS: Set[str] = {
    'noqa', 'ignore', 'skipline', 'no-check', 'suppress', 'disable'
}

QA_TAGS: Dict[str, str] = {
    'TODO': 'INFO', 'FIXME': 'WARNING', 'BUG': 'ERROR', 
    'HACK': 'WARNING', 'XXX': 'CRITICAL', 'ADTI': 'CRITICAL'
}

FACADE_FILES: Set[str] = {'shared_tools.py', '__init__.py'}

def _is_silenced(line_content: str) -> bool:
    """Verifica se a linha possui tags de silenciamento (# noqa)."""
    if '#' not in line_content:
        return False
    comment = line_content.split('#', 1)[1].strip().lower()
    return any(tag in comment for tag in SILENCERS)

def _is_facade_fp(message: str, filename: str, category: str) -> bool:
    """Identifica falsos positivos em arquivos de Fachada."""
    if filename not in FACADE_FILES:
        return False
    msg_lower = message.lower()
    return 'unused' in msg_lower or 'redefinition' in msg_lower or category == 'DEADCODE'

def filter_and_inject_findings(findings: List[Dict[str, Any]], project_root: str) -> List[Dict[str, Any]]:
    """
    Filtra achados e injeta TODOs com cache de linhas (PASC-6.4).
    """
    final_findings = []
    # Cache para evitar múltiplas aberturas do mesmo arquivo (Otimização de RAM)
    file_cache: Dict[str, List[str]] = {}

    # 1. Processamento e Filtragem
    for f in findings:
        file_path = f.get('file')
        if not file_path:
            continue

        abs_path = os.path.abspath(file_path)
        filename = os.path.basename(abs_path)
        cat = f.get('category', '').upper()
        msg = f.get('message', '')
        line_num = f.get('line')

        # Filtro de Fachada imediato
        if _is_facade_fp(msg, filename, cat):
            continue

        # Carregamento inteligente de linhas
        if abs_path not in file_cache:
            file_cache[abs_path] = _load_file_lines(abs_path)
        
        lines = file_cache[abs_path]

        # Filtro de Silenciamento (# noqa)
        if line_num and 0 < line_num <= len(lines):
            if _is_silenced(lines[line_num - 1]):
                continue

        final_findings.append(f)

    # 2. Injeção de Lembretes (TODO/ADTI)
    # Varre apenas os arquivos que já estão no cache (arquivos que foram auditados)
    for path, lines in file_cache.items():
        final_findings.extend(_extract_qa_reminders(lines, path))

    return final_findings

def _load_file_lines(file_path: str) -> List[str]:
    """Lê o arquivo de forma segura (MPoT-18)."""
    if not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()
    except Exception:
        return []

def _extract_qa_reminders(lines: List[str], file_path: str) -> List[Dict[str, Any]]:
    """Varre as linhas em busca de tags de QA."""
    reminders = []
    for i, line in enumerate(lines):
        if '#' not in line: continue
        
        comment_part = line.split('#', 1)[1].strip()
        tokens = comment_part.split()
        if not tokens: continue
            
        tag = tokens[0].upper().rstrip(':')
        if tag in QA_TAGS:
            # Proteção contra auto-ignição
            if any(s in comment_part.lower() for s in ['asis', 'ignore-todo']):
                continue

            reminders.append({
                'severity': QA_TAGS[tag],
                'category': 'QA-REMINDER',
                'message': f"[{tag}] {comment_part[len(tag):].strip().lstrip(':').strip()}",
                'file': file_path,
                'line': i + 1,
                'snippet': _get_code_snippet(file_path, i + 1)
            })
    return reminders