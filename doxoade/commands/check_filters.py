# doxoade/commands/check_filters.py

import os
from ..shared_tools import _get_code_snippet

SILENCERS = {
    'noqa', 'numerator', 'ignore', 'skipline', 'asis', 'no-check',
    'suppress', 'disable', 'dtiw', 'igfi'
}

QA_TAGS = {
    'TODO': 'INFO',
    'FIXME': 'WARNING',
    'BUG': 'ERROR',
    'HACK': 'WARNING',
    'XXX': 'CRITICAL',
    'CKQA': 'WARNING',
    'VYQA': 'INFO',
    'ADTI': 'CRITICAL',
    'QA-CHECK': 'WARNING'
}

# Arquivos que agem como Fachada (Facade Pattern)
# Neles, "imported but unused" é uma feature, não um bug.
FACADE_FILES = {'shared_tools.py', '__init__.py'}

def filter_and_inject_findings(findings, file_path):
    # [FIX] Proteção robusta: Se não houver arquivo, retorna a lista original sem processar TODOs
    if not file_path:
        return findings

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except IOError:
        return findings

    final_findings = []
    
    # Identifica se é um arquivo de fachada
    filename = os.path.basename(file_path)
    is_facade = filename in FACADE_FILES

    # 1. Filtra erros silenciados e falsos positivos estruturais
    for f in findings:
        message = f.get('message', '').lower()
        category = f.get('category', '').upper()
        
        # --- FILTRO DE FACHADA (FACADE FILTER) ---
        # Se for shared_tools ou __init__, ignora "imported but unused"
        if is_facade:
            if 'imported but unused' in message or 'unused import' in message:
                continue
            # Ignora redefinições se for apenas re-exportação
            if 'redefinition of' in message:
                continue

        line_num = f.get('line')
        if not line_num or not isinstance(line_num, int) or line_num > len(lines):
            final_findings.append(f)
            continue
            
        line_content = lines[line_num - 1]
        is_silenced = False
        
        # Verifica tags de silenciamento na linha (# noqa, etc)
        if '#' in line_content:
            comment = line_content.split('#', 1)[1].strip().lower()
            for tag in SILENCERS:
                if tag in comment:
                    is_silenced = True
                    break
        
        if not is_silenced:
            final_findings.append(f)

    # 2. Injeta lembretes de QA (TODOs)
    for i, line in enumerate(lines):
        if '#' in line:
            parts = line.split('#', 1)
            if len(parts) < 2: continue
            
            comment_part = parts[1].strip()
            if not comment_part: continue

            # Pega a primeira palavra do comentário (ex: "TODO:" -> "TODO")
            first_word_raw = comment_part.split()[0]
            first_word = first_word_raw.upper().rstrip(':')
            
            if first_word in QA_TAGS:
                final_findings.append({
                    'severity': QA_TAGS[first_word],
                    'category': 'QA-REMINDER',
                    'message': f"[{first_word}] {comment_part[len(first_word):].strip().lstrip(':').strip()}",
                    'file': file_path,
                    'line': i + 1,
                    'snippet': _get_code_snippet(file_path, i + 1)
                })

    return final_findings