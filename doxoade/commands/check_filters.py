# doxoade/commands/check_filters.py (Versão Gold)

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
    # Captura tudo após o primeiro #
    comment = line_content.split('#', 1)[1].strip().lower()
    return any(tag in comment for tag in SILENCERS)

def _is_facade_fp(message: str, filename: str, category: str) -> bool:
    """Identifica falsos positivos em arquivos de Fachada."""
    if filename not in FACADE_FILES:
        return False
    
    msg_lower = message.lower()
    # Em fachadas, imports não usados ou redefinições são normais
    if 'unused' in msg_lower or 'redefinition' in msg_lower or category == 'DEADCODE':
        return True
    return False

def filter_and_inject_findings(findings: List[Dict[str, Any]], file_path: str) -> List[Dict[str, Any]]:
    """
    Filtra achados baseados em comentários e tipo de arquivo.
    Injeta lembretes de QA baseados em comentários.
    """
    if not file_path or not os.path.exists(file_path):
        return findings

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except (IOError, PermissionError):
        return findings

    filename = os.path.basename(file_path)
    final_findings = []

    for f in findings:
        msg = f.get('message', '')
        cat = f.get('category', '').upper()
        line_num = f.get('line')

        # 1. Filtro de Fachada
        if _is_facade_fp(msg, filename, cat):
            continue

        # 2. Filtro de Silenciamento (# noqa)
        if line_num and isinstance(line_num, int) and 0 < line_num <= len(lines):
            if _is_silenced(lines[line_num - 1]):
                continue

        final_findings.append(f)

    # 3. Injeção de TODOs
    for i, line in enumerate(lines):
        if '#' in line:
            comment_part = line.split('#', 1)[1].strip()
            tokens = comment_part.split()
            if tokens:
                tag = tokens[0].upper().rstrip(':')
                if tag in QA_TAGS:
                    final_findings.append({
                        'severity': QA_TAGS[tag],
                        'category': 'QA-REMINDER',
                        'message': f"[{tag}] {comment_part[len(tag):].strip().lstrip(':').strip()}",
                        'file': file_path,
                        'line': i + 1,
                        'snippet': _get_code_snippet(file_path, i + 1)
                    })

    return final_findings
    
def _extract_qa_reminders(lines: List[str], file_path: str) -> List[Dict[str, Any]]:
    """Varre o arquivo em busca de tags, ignorando falsos positivos."""
    reminders = []
    
    # TODO: Futura implementação - Usar tokenize para ignorar TODOs dentro de strings
    
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if '#' not in clean_line: continue
        
        # Ignora se o # estiver dentro de uma string (heurística simples)
        if clean_line.count('"') >= 2 or clean_line.count("'") >= 2:
            if clean_line.find('#') > clean_line.find('"') or clean_line.find('#') > clean_line.find("'"):
                continue

        parts = line.split('#', 1)
        comment_part = parts[1].strip()
        
        tokens = comment_part.split()
        if not tokens: continue
            
        tag = tokens[0].upper().rstrip(':')
        
        # Só injeta se a tag for isolada e permitida
        if tag in QA_TAGS:
            # Proteção: Ignora se houver a tag 'asis' ou 'ignore' no próprio comentário
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