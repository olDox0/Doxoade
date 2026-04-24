# doxoade/doxoade/commands/mk_systems/mk_utils.py
import os
import re
import subprocess


TREE_BRANCH = '├── '
TREE_LAST = '└── '
TREE_INDENT = '│   '

def get_tree_icon(is_dir: bool) -> str:
    """Ícones de alta visibilidade para terminais modernos."""
    return '📁 ' if is_dir else '📄 '

def is_directory(path_name: str) -> bool:
    """Detecta se o alvo é diretório de forma mais conservadora."""
    clean_name = path_name.strip().replace('\\', '/').rstrip(' ')
    basename = os.path.basename(clean_name.rstrip('/'))
    if clean_name.endswith('/'): return True
    
    known_files = ['Dockerfile', 'Makefile', 'LICENSE', 'PROCFILE', 'README', 'CHANGELOG', '.env']
    if basename.upper() in known_files or basename.startswith('.'):
        return False
    return '.' not in basename

def clean_path_and_content(line: str):
    """Extrai path e conteúdo de strings tipo 'file.txt[conteúdo]'."""
    line = line.strip().replace('\\', '/')
    match = re.search('^([^\\\\[]+)\\[(.*)\\](.*)$', line)
    if match:
        path = f'{match.group(1).strip()}{match.group(3).strip()}'
        content = match.group(2).replace('\\n', '\n').replace('/n', '\n')
        return (path, content)
    return (line, '')

def expand_braces(text: str) -> list:
    """Expande sintaxe de chaves: folder/{a.py,b.py} -> [folder/a.py, folder/b.py]."""
    match = re.search('^(.*)\\{(.*)\\}(.*)$', text)
    if not match:
        return [text]
    prefix, content, suffix = match.groups()
    parts = [p.strip() for p in content.split(',')]
    return [f'{prefix}{p}{suffix}' for p in parts]

def open_in_notepadpp(file_paths: list):
    """Abre arquivos no Notepad++, tentando encontrar o executável se não estiver no PATH."""
    if not file_paths:
        return
    
    # Lista de possíveis locais do executável
    npp_candidates = [
        'notepad++', # Tenta o PATH primeiro
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe"
    ]
    
    executable = None
    for candidate in npp_candidates:
        # Se for apenas o nome, o shutil.which verifica o PATH
        import shutil
        if shutil.which(candidate) or os.path.exists(candidate):
            executable = candidate
            break

    if not executable:
        print("[-] Erro: Notepad++ não encontrado no PATH ou nos locais padrão.")
        return

    try:
        files = list(dict.fromkeys([os.path.abspath(f) for f in file_paths if os.path.isfile(f)]))
        if files:
            # Usa subprocess.Popen para não travar o terminal
            subprocess.Popen([executable, *files])
    except Exception as e:
        print(f"[-] Erro ao disparar editor: {e}")

def get_indent_level(line: str) -> int:
    """Calcula o nível de indentação convertendo tabs em 4 espaços (PASC 6.3)."""
    expanded_line = line.replace('\t', '    ')
    return len(expanded_line) - len(expanded_line.lstrip())