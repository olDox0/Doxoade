# -*- coding: utf-8 -*-
# doxoade/commands/search_systems/search_utils.py
"""Especialista em Blocos de Código e Busca Histórica (MPoT-4)."""
import os
import subprocess
from click import echo
from doxoade.tools.doxcolors import Fore, Style
from .search_state import SearchState
def render_search_results(state: 'SearchState'):
    """Interface Forense Unificada (Chief-Style)."""
    if state.matches:
        echo(f"{Fore.CYAN}{Style.BRIGHT}\n[Código & Docs]{Style.RESET_ALL}")
        
        for m in state.matches:
            is_py = m['type'] == '.py'
            color = Fore.BLUE if is_py else Fore.MAGENTA
            echo(f"{color} [{m['type'].upper()}] {m['file']}:{m['line']}{Style.RESET_ALL}")
            
            # DECISÃO DE VISÃO: Bloco Completo ou Snippet?
            if state.is_full_mode and is_py:
                block = extract_function_block(os.path.join(state.root, m['file']), m['line'])
                if block:
                    for line in block.splitlines():
                        # Realça a linha que contém o match original
                        is_target = f":{m['line']}:" in f":{line.split(':')[0] if ':' in line else ''}:"
                        s_color = Fore.WHITE + Style.BRIGHT if is_target else Style.DIM
                        echo(f"    {s_color}{line}{Style.RESET_ALL}")
                    echo("")
                    continue
            # Fallback para Snippet Normal
            from ...tools.analysis import _get_code_snippet
            snippet = _get_code_snippet(os.path.join(state.root, m['file']), m['line'])
            for snip_line, snip_text in sorted(snippet.items()):
                is_target = (int(snip_line) == m['line'])
                prefix = "      > " if is_target else "        "
                s_color = Fore.WHITE + Style.BRIGHT if is_target else Fore.WHITE + Style.DIM
                echo(f"{s_color}{prefix}{snip_line:4}: {snip_text}{Style.RESET_ALL}")
    # 2. Banco de Dados
    if state.db_results['incidents']:
        echo(f"{Fore.RED}{Style.BRIGHT}\n╔═══ Incidentes Ativos ═══╗{Style.RESET_ALL}")
        for inc in state.db_results['incidents']:
            echo(f"{Fore.YELLOW}[{inc['category']}] {Fore.WHITE}{inc['message']}{Style.RESET_ALL}")
            echo(f"  Em: {inc['file']}:{inc['line']}")
    # 3. Timeline Chronos
    if state.timeline:
        echo(f"{Fore.MAGENTA}{Style.BRIGHT}\n╔═══ Timeline (Chronos) ═══╗{Style.RESET_ALL}")
        for t in state.timeline:
            status = f"{Fore.GREEN}✔" if t['exit_code'] == 0 else f"{Fore.RED}✘"
            echo(f" {status} {Fore.WHITE}{t['timestamp'][:19]} | {Fore.CYAN}{t['full_line']}{Style.RESET_ALL}")
            
    # 4. Verificação de Vácuo (MPoT-15)
    has_results = any([state.matches, state.timeline, 
                      state.db_results['incidents'], state.db_results['solutions'],
                      state.git_results])
    if not has_results:
        echo(f"\n{Fore.YELLOW}   [!] Nenhum resultado encontrado para '{state.query}' nos filtros ativos.{Style.RESET_ALL}")
def extract_function_block(file_path: str, match_line: int) -> str:
    """Extrai o bloco lógico (def/class) escaneando para cima e para baixo (PASC-8.10)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        match_idx = match_line - 1
        if match_idx >= len(lines): return ""
        # 1. SCAN UP: Encontra o início da função/classe
        start_idx = match_idx
        while start_idx > 0:
            line = lines[start_idx].strip()
            # Se encontrar um def/class com indentação menor ou igual, paramos
            if line.startswith(('def ', 'class ', '@')):
                break
            start_idx -= 1
        
        # 2. CAPTURA INDENTAÇÃO BASE
        base_line = lines[start_idx]
        indent = len(base_line) - len(base_line.lstrip())
        
        # 3. SCAN DOWN: Encontra o fim do bloco
        block = []
        for i in range(start_idx, len(lines)):
            line = lines[i]
            if not line.strip(): # Pula linhas vazias
                block.append(line.rstrip())
                continue
            
            curr_indent = len(line) - len(line.lstrip())
            if curr_indent <= indent: # Fim do bloco (voltou para a indentação original)
                break
            block.append(line.rstrip())
            
        return "\n".join(block)
    except Exception: return "Erro ao extrair bloco."
def search_git_history_content(query: str, limit: int = 5) -> list:
    """Busca quando uma string foi adicionada ou removida no passado (Pickaxe Search)."""
    # -S busca por mudanças no número de ocorrências da string (perfeito para funções)
    cmd = ['git', 'log', f'-S{query}', '--oneline', f'-n{limit}']
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', shell=False)
        if res.returncode != 0: return []
        
        commits = []
        for line in res.stdout.splitlines():
            parts = line.split(' ', 1)
            if len(parts) == 2:
                commits.append({'hash': parts[0], 'msg': parts[1]})
        return commits
    except Exception: return []
def get_code_from_commit(commit_hash: str, query: str) -> list:
    """Busca cirúrgica no Git com tratamento de múltiplas linhas (MPoT-7)."""
    import subprocess
    # Injetamos o filtro de exclusão para não pesquisar em lixo binário ou snapshots
    cmd = [
        'git', 'grep', '-n', '-i', '-e', query, commit_hash, 
        '--', '*.py', '*.md', ':(exclude).doxoade/*'
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', shell=False)
        if res.returncode != 0: return []
        
        matches = []
        for line in res.stdout.splitlines():
            # hash:path:line:content
            parts = line.split(':', 3)
            if len(parts) >= 4:
                matches.append({
                    'file': parts[1],
                    'line': parts[2],
                    'text': parts[3].strip()
                })
        return matches
    except Exception: return []
    
def extract_block_from_git(commit_hash: str, file_path: str, start_line: int) -> str:
    """Extrai bloco histórico garantindo path relativo à raiz do Git (Aegis Pattern)."""
    from ...shared_tools import _find_project_root
    project_root = _find_project_root(os.getcwd())
    
    # NORMALIZAÇÃO DE PATH (Vital para Windows/Git)
    abs_file = os.path.abspath(file_path)
    rel_git_path = os.path.relpath(abs_file, project_root).replace('\\', '/')
    
    cmd = ['git', 'show', f'{commit_hash}:{rel_git_path}']
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', shell=False)
        if res.returncode != 0: 
            return f"Erro: {rel_git_path} não consta no commit {commit_hash}."
        
        lines = res.stdout.splitlines()
        # Aqui aplicaríamos a mesma lógica de Scan Up/Down nos 'lines' se necessário
        target_idx = int(start_line) - 1
        if target_idx < 0 or target_idx >= len(lines): return ""
        # 2. Lógica de Indentação Industrial (MPoT-4)
        base_line = lines[target_idx]
        # Se a linha não for um início de bloco (def/class), tenta achar o início acima
        if not any(base_line.strip().startswith(x) for x in ['def ', 'class ', '@']):
             # Apenas mostra a linha se não for um bloco lógico
             return f"    {base_line.strip()}"
        indent = len(base_line) - len(base_line.lstrip())
        block = [base_line]
        
        for i in range(target_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip(): # Preserva espaços em branco
                block.append(line)
                continue
            curr_indent = len(line) - len(line.lstrip())
            # Se a indentação voltou ao nível do 'def', o bloco acabou
            if curr_indent <= indent and line.strip():
                break
            block.append(line)
        return "\n".join([f"{i+1:4}: {l}" for i, l in enumerate(lines[max(0, target_idx-5):target_idx+15])])
    except Exception as e:
        return f"Falha na arqueologia: {e}"
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)