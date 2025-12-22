# doxoade/commands/check_filters.py
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

def filter_and_inject_findings(findings, file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except IOError:
        return findings

    final_findings = []
    
    # 1. Filtra erros silenciados
    for f in findings:
        line_num = f.get('line')
        if not line_num or line_num > len(lines):
            final_findings.append(f)
            continue
            
        line_content = lines[line_num - 1]
        is_silenced = False
        
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
            comment_part = parts[1].strip()
            
            # Pega a primeira palavra do comentário (ex: "TODO:" -> "TODO")
            first_word_raw = comment_part.split()[0] if comment_part else ""
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