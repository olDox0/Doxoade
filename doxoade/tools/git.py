# doxoade/tools/git.py
import subprocess
import os
import re
from colorama import Fore

def _run_git_command(args, capture_output=False, silent_fail=False):
    """Executa um comando git de forma segura e codificada."""
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        command = ['git'] + args
        
        result = subprocess.run(
            command, capture_output=capture_output, text=True, check=True,
            encoding='utf-8', errors='replace', env=env
        )
        return result.stdout.strip() if capture_output else True
    except (FileNotFoundError, subprocess.CalledProcessError):
        if not silent_fail:
            if not capture_output: 
                print(Fore.RED + "[ERRO GIT] O comando falhou.")
        return None

def _get_git_commit_hash(path):
    """Obtém o hash do commit atual no diretório especificado."""
    original_dir = os.getcwd()
    try:
        if os.path.exists(path):
            os.chdir(path)
        hash_output = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        return hash_output if hash_output else "N/A"
    except Exception: 
        return "N/A"
    finally: 
        os.chdir(original_dir)
        
def _get_detailed_diff_stats(show_code: bool = False, target_path: str = None):
    """
    Parser de Estados Estrito (MPoT-1). 
    Garante que metadados do Git não vazem para o relatório semântico.
    """
    from .git import _run_git_command # PASC-6.1

    # 1. Coleta de estatísticas brutas
    num_args = ["diff", "--numstat"]
    if target_path: num_args.extend(["--", target_path])
    numstat_raw = _run_git_command(num_args, capture_output=True, silent_fail=True)
    
    line_counts = {}
    if numstat_raw:
        for line in numstat_raw.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                line_counts[parts[2]] = {'added': int(parts[0]), 'removed': int(parts[1])}

    # 2. Execução do Diff com controle de contexto
    diff_args = ["diff", "-U1" if show_code else "-U0", "--no-color"]
    if target_path: diff_args.extend(["--", target_path])
    diff_raw = _run_git_command(diff_args, capture_output=True, silent_fail=True)
    
    changes = []
    current_file = None
    ln_plus, ln_minus = 0, 0
    
    # Regexes de precisão
    hunk_pattern = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
    func_pattern = re.compile(r'^[+-]\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)')
    comment_pattern = re.compile(r'^([+-])\s*#\s*(.*)')

    if diff_raw:
        for line in diff_raw.splitlines():
            # ESTADO: Mudança de Arquivo
            if line.startswith('+++ b/'):
                path = line[6:]
                current_file = {
                    'path': path,
                    'added': line_counts.get(path, {}).get('added', 0),
                    'removed': line_counts.get(path, {}).get('removed', 0),
                    'functions': {}, 'comments': [], 'hunks': []
                }
                changes.append(current_file)
                continue
            
            # IGNORAR: Outros metadados do Git
            if line.startswith(('diff --git', 'index ', '--- a/', 'old mode', 'new mode')):
                continue

            if not current_file: continue

            # ESTADO: Novo Bloco (Hunk)
            hunk_match = hunk_pattern.match(line)
            if hunk_match:
                ln_minus = int(hunk_match.group(1))
                ln_plus = int(hunk_match.group(2))
                continue

            # ESTADO: Adição (+)
            if line.startswith('+'):
                f_match = func_pattern.match(line)
                if f_match:
                    name = f_match.group(1)
                    current_file['functions'][name] = {'type': '+', 'line': ln_plus}
                
                c_match = comment_pattern.match(line)
                if c_match:
                    current_file['comments'].append({
                        'text': c_match.group(2).strip(), 
                        'line': ln_plus, 
                        'type': '+'
                    })
                
                if show_code: 
                    current_file['hunks'].append({'line': ln_plus, 'content': line, 'type': 'add'})
                ln_plus += 1

            # ESTADO: Remoção (-)
            elif line.startswith('-'):
                f_match = func_pattern.match(line)
                if f_match:
                    name = f_match.group(1)
                    # Se já existia na mesma diff, é uma modificação (*)
                    if name in current_file['functions']:
                        current_file['functions'][name]['type'] = '*'
                    else:
                        current_file['functions'][name] = {'type': '-', 'line': ln_minus}
                
                # Rastreio de remoção de comentários (para modo -cm)
                c_match = comment_pattern.match(line)
                if c_match:
                    current_file['comments'].append({
                        'text': c_match.group(2).strip(), 
                        'line': ln_minus, 
                        'type': '-'
                    })

                if show_code: 
                    current_file['hunks'].append({'line': ln_minus, 'content': line, 'type': 'rem'})
                ln_minus += 1

            # ESTADO: Contexto (Somente se show_code estiver ativo)
            elif show_code and not line.startswith('\\'):
                current_file['hunks'].append({'line': ln_plus, 'content': line, 'type': 'ctx'})
                ln_plus += 1
                ln_minus += 1

    # Finalização semântica
    for c in changes:
        c['functions'] = [{'name': k, **v} for k, v in c['functions'].items()]
        
    return changes
    
def _get_last_commit_info():
    """Retorna informações detalhadas do último commit (Chief-Style)."""
    fmt = "%h|%an|%as|%s" # hash | author | date | subject
    raw = _run_git_command(['log', '-1', f'--format={fmt}'], capture_output=True, silent_fail=True)
    if not raw: return None
    parts = raw.strip().split('|')
    if len(parts) < 4: return None
    return {
        "hash": parts[0],
        "author": parts[1],
        "date": parts[2],
        "subject": parts[3]
    }
    
def _get_file_history_metadata(path: str, limit: int = 10):
    """
    Recupera metadados dos últimos commits que afetaram o arquivo (PASC-1.1).
    """
    # Formato: hash|data|autor|mensagem
    fmt = "%h|%as|%an|%s"
    cmd = ['log', f'-{limit}', f'--format={fmt}', '--', path]
    raw = _run_git_command(cmd, capture_output=True, silent_fail=True)
    
    history = []
    if raw:
        for line in raw.splitlines():
            parts = line.split('|')
            if len(parts) >= 4:
                history.append({
                    'hash': parts[0],
                    'date': parts[1],
                    'author': parts[2],
                    'subject': parts[3]
                })
    return history

def _get_historical_content(path: str, commit_hash: str) -> str:
    """Recupera o conteúdo de um arquivo em um ponto específico do tempo."""
    return _run_git_command(['show', f'{commit_hash}:{path}'], capture_output=True, silent_fail=True) or ""