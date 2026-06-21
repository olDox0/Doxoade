# doxoade/commands/search_systems/search_diff.py
"""
Motor de Busca em Diffs, Commits e Arquivos Deletados (PASC 8.12).
Disponibiliza buscas por símbolos históricos (Pickaxe) e rastreamento textual de alta velocidade.
"""
import os
import re
import subprocess
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.telemetry_tools.logger import chief_heartbeat

def search_git_diffs_pickaxe(query: str, file_path: str = None) -> list:
    """
    Busca acréscimos (+) ou deleções (-) de uma query ao longo do histórico (Git Pickaxe).
    """
    project_root = _find_project_root(os.path.dirname(os.path.abspath(file_path))) if file_path else os.getcwd()
    if not project_root:
        chief_heartbeat("HORUS", "SEARCH_DIFF_ERROR", {
            "query": query,
            "error": "Incapaz de localizar a raiz do projeto Git para Pickaxe."
        })
        return []

    cmd = ['git', 'log', '-S', query, '--patch', '--oneline']
    if file_path:
        rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
        cmd.extend(['--', rel_path])

    try:
        res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if res.returncode == 0:
            commits = []
            current = None
            for line in res.stdout.splitlines():
                if re.match(r'^[0-9a-f]{7,40}\s', line):
                    parts = line.split(' ', 1)
                    current = {
                        'hash': parts[0],
                        'summary': parts[1] if len(parts) > 1 else '',
                        'matches': []
                    }
                    commits.append(current)
                elif current and (line.startswith('+') or line.startswith('-')) and not (line.startswith('+++') or line.startswith('---')):
                    if query.lower() in line.lower():
                        current['matches'].append({'type': 'ADD' if line.startswith('+') else 'DEL', 'content': line[1:].strip()})
            return [c for c in commits if c['matches']]
        else:
            chief_heartbeat("HORUS", "SEARCH_DIFF_ERROR", {
                "query": query,
                "exit_code": res.returncode,
                "stderr": res.stderr.strip()
            })
    except Exception as e:
        chief_heartbeat("HORUS", "SEARCH_DIFF_ERROR", {
            "query": query,
            "error": str(e)
        })
    return []

def search_commit_grep(query: str, commit_hash: str, file_path: str = None) -> list:
    """Busca um termo dentro de todos os arquivos de um commit via Git Grep."""
    project_root = _find_project_root(os.path.dirname(os.path.abspath(file_path))) if file_path else os.getcwd()
    if not project_root:
        chief_heartbeat("HORUS", "SEARCH_COMMIT_ERROR", {
            "query": query,
            "commit": commit_hash,
            "error": "Incapaz de localizar a raiz do projeto Git para Grep."
        })
        return []

    cmd = ['git', 'grep', '-n', query, commit_hash]
    if file_path:
        rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
        cmd.extend(['--', rel_path])

    try:
        res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        results = []
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    results.append({
                        'commit': parts[0],
                        'file': parts[1],
                        'line': int(parts[2]) if parts[2].isdigit() else 0,
                        'text': parts[3].strip()
                    })
            return results
        else:
            chief_heartbeat("HORUS", "SEARCH_COMMIT_ERROR", {
                "query": query,
                "commit": commit_hash,
                "exit_code": res.returncode,
                "stderr": res.stderr.strip()
            })
    except Exception as e:
        chief_heartbeat("HORUS", "SEARCH_COMMIT_ERROR", {
            "query": query,
            "commit": commit_hash,
            "error": str(e)
        })
    return []

def search_deleted_files(query: str) -> list:
    """
    Busca arquivos que foram deletados do repositório Git de forma otimizada (PASC 8.15).
    Evita loops sequenciais de subprocessos filtrando candidatos antecipadamente.
    """
    project_root = _find_project_root(os.getcwd())
    if not project_root:
        chief_heartbeat("HORUS", "SEARCH_DELETED_ERROR", {
            "query": query,
            "error": "Incapaz de localizar a raiz do projeto Git."
        })
        return []

    # 1. Busca rápida por nome: obtém a lista de caminhos de todos os arquivos deletados
    cmd = ['git', 'log', '--diff-filter=D', '--name-only', '--pretty=format:']
    candidate_files = []
    try:
        res = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if res.returncode == 0:
            all_deleted = set([line.strip() for line in res.stdout.splitlines() if line.strip()])
            # Pré-filtra candidatos pelo nome do arquivo/caminho (Otimização de Escala!)
            candidate_files = [f for f in all_deleted if query.lower() in f.lower()]
    except Exception as e:
        chief_heartbeat("HORUS", "SEARCH_DELETED_ERROR", {"query": query, "error": str(e)})
        return []

    # 2. Caso de Busca de Conteúdo histórica rápida (Git Pickaxe para Deleções)
    if not candidate_files:
        pickaxe_cmd = ['git', 'log', '-S', query, '--diff-filter=D', '--name-only', '--pretty=format:']
        try:
            pick_res = subprocess.run(pickaxe_cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if pick_res.returncode == 0:
                candidate_files = sorted(list(set([line.strip() for line in pick_res.stdout.splitlines() if line.strip()])))
        except Exception:
            pass

    if not candidate_files:
        return []

    results = []
    # Agora executamos os subprocessos APENAS para os arquivos pré-filtrados altamente relevantes
    for rel_path in candidate_files[:20]:  # Limita a 20 candidatos para segurança de performance
        match_by_name = query.lower() in rel_path.lower()
        
        # Encontra o commit específico em que o arquivo foi deletado com metadados ricos
        commit_cmd = ['git', 'log', '-1', '--diff-filter=D', '--pretty=format:%H|%an|%ad|%s', '--date=format:%Y-%m-%d %H:%M', '--', rel_path]
        commit_res = subprocess.run(commit_cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if commit_res.returncode != 0 or not commit_res.stdout.strip():
            continue
            
        parts = commit_res.stdout.strip().split('|', 3)
        deletion_commit = parts[0] if len(parts) > 0 else 'unknown'
        author = parts[1] if len(parts) > 1 else 'unknown'
        date_str = parts[2] if len(parts) > 2 else 'unknown'
        summary = parts[3] if len(parts) > 3 else 'No message'
        
        # Recupera o conteúdo do arquivo no commit imediatamente anterior à deleção (usando o pai '^')
        show_cmd = ['git', 'show', f'{deletion_commit}^:{rel_path}']
        show_res = subprocess.run(show_cmd, cwd=project_root, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if show_res.returncode == 0:
            content = show_res.stdout
            lines = content.splitlines()
            
            # Busca pelo termo pesquisado no corpo do arquivo excluído
            match_lines = []
            for idx, line in enumerate(lines):
                if query.lower() in line.lower():
                    match_lines.append((idx + 1, line.strip()))
            
            if match_by_name or match_lines:
                # Extrai amostra/snippet contextuais
                sample = {}
                if match_lines:
                    target_line = match_lines[0][0]
                    start = max(0, target_line - 3)
                    end = min(len(lines), target_line + 3)
                    for i in range(start, end):
                        sample[str(i + 1)] = lines[i]
                else:
                    # Caso de busca por nome, pega as primeiras 10 linhas do topo
                    for i in range(min(10, len(lines))):
                        sample[str(i + 1)] = lines[i]
                        
                results.append({
                    'file': rel_path,
                    'commit': deletion_commit,
                    'author': author,
                    'date': date_str,
                    'summary': summary,
                    'match_by_name': match_by_name,
                    'sample': sample,
                    'occurrences': len(match_lines)
                })
                
    return results