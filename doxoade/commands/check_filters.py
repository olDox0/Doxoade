# doxoade/commands/check_filters.py
from ..shared_tools import _get_code_snippet

# Lista de tags que silenciam erros
SILENCERS = {
    'noqa', 'numerator', 'ignore', 'skipline', 'asis', 'no-check', 
    'suppress', 'disable', 'dtiw', 'igfi'
}

# Lista de tags que CRIAM avisos (Lembretes de QA)
QA_TAGS = {
    'TODO': 'INFO',
    'FIXME': 'WARNING',
    'BUG': 'ERROR',
    'HACK': 'WARNING',
    'XXX': 'CRITICAL',
    'CKQA': 'WARNING',      # Check Quality Assurance
    'VYQA': 'INFO',         # Verify QA
    'ADTI': 'CRITICAL',     # Always Display This Issue
    'QA-CHECK': 'WARNING'   # Nome intuitivo universal
}

def filter_and_inject_findings(findings, file_path):
    """
    (Refatorado)
    1. Filtra findings se a linha tiver diretivas de silêncio (# noqa).
    2. Injeta novos findings se encontrar tags de QA (# TODO, # FIXME).
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except IOError:
        return findings

    final_findings = []
    
    # 1. FILTRAGEM (Supressão)
    for f in findings:
        line_num = f.get('line')
        # Se não tem linha (erro global) ou linha fora do range, mantém
        if not line_num or line_num > len(lines):
            final_findings.append(f)
            continue
            
        line_content = lines[line_num - 1]
        
        # Verifica se tem silenciador
        is_silenced = False
        if '#' in line_content:
            comment = line_content.split('#', 1)[1].strip().upper()
            for tag in SILENCERS:
                if tag.upper() in comment:
                    is_silenced = True
                    break
        
        if not is_silenced:
            final_findings.append(f)

    # 2. INJEÇÃO (QA Tags)
    for i, line in enumerate(lines):
        if '#' in line:
            comment_part = line.split('#', 1)[1].strip()
            # Pega primeira palavra (ex: TODO:)
            first_word = comment_part.split(':')[0].split()[0].upper().rstrip(':')
            
            if first_word in QA_TAGS:
                msg = comment_part[len(first_word):].strip().lstrip(':').strip()
                if not msg: msg = "Lembrete de QA sem descrição."
                
                final_findings.append({
                    'severity': QA_TAGS[first_word],
                    'category': 'QA-REMINDER',
                    'message': f"[{first_word}] {msg}",
                    'file': file_path,
                    'line': i + 1,
                    'snippet': _get_code_snippet(file_path, i + 1)
                })

    return final_findings