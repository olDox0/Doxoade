# -*- coding: utf-8 -*-
# doxoade/commands/search_systems/search_utils.py
"""Especialista em Blocos de Código e Busca Histórica (MPoT-4)."""
import subprocess

def extract_function_block(file_path: str, start_line: int) -> str:
    """Extrai o bloco inteiro de uma função baseando-se na indentação (PASC-6.4)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        target_idx = start_line - 1
        if target_idx >= len(lines): return ""
        
        base_line = lines[target_idx]
        # Detecta indentação inicial (espaços ou tabs)
        indent = len(base_line) - len(base_line.lstrip())
        
        block = [base_line.rstrip()]
        for i in range(target_idx + 1, len(lines)):
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
    """Extrai o bloco de código de um commit (PASC-1.1)."""
    # 1. Recupera o arquivo integral daquele snapshot
    cmd = ['git', 'show', f'{commit_hash}:{file_path}']
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', shell=False)
        if res.returncode != 0: return f"{file_path} não encontrado no commit {commit_hash}."
        
        lines = res.stdout.splitlines()
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
            
        return "\n".join(block)
    except Exception as e:
        return f"Falha na extração histórica: {e}"