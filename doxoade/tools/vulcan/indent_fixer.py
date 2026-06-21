# doxoade/tools/vulcan/indent_fixer.py
import re
import os

def perform_indent_surgery(file_path):
    """Detecta e corrige linhas com 1 a 3 espaços injetadas erroneamente."""
    if not os.path.exists(file_path): return False
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    new_lines = []
    changed = False
    
    for i, line in enumerate(lines):
        # Alvo: Linhas que começam com espaços curtos (1-3) seguidos de código injetado
        match = re.match(r"^(\s{1,3})(import|from|_dox|chief_heartbeat|try:|except|finally)", line)
        
        if match:
            # Tenta descobrir o recuo do bloco atual (olhando para cima)
            correct_indent = ""
            for prev_idx in range(i - 1, -1, -1):
                prev_line = lines[prev_idx]
                if prev_line.strip() and not prev_line.strip().startswith('#'):
                    indent_match = re.match(r"^(\s*)", prev_line)
                    correct_indent = indent_match.group(1) if indent_match else ""
                    # Se a linha anterior termina em ':', o nível atual deve ser +4
                    if prev_line.strip().endswith(':'):
                        correct_indent += "    "
                    break
            
            cleaned_line = correct_indent + line.lstrip()
            if cleaned_line != line:
                new_lines.append(cleaned_line)
                changed = True
                continue
        
        new_lines.append(line)

    if changed:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False