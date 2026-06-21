# doxoade/doxoade/tools/git.py
import subprocess
import os
import re
from doxoade.tools.doxcolors import Fore

def _run_git_command(args, capture_output=False, silent_fail=False, cwd=None):
    """Executa um comando git de forma segura e codificada."""
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        command = ['git'] + args
        result = subprocess.run(command, capture_output=capture_output, text=True, check=True, encoding='utf-8', errors='replace', env=env, cwd=cwd)
        return result.stdout.strip() if capture_output else True
    except (FileNotFoundError, subprocess.CalledProcessError):
        if not silent_fail:
            if not capture_output:
                print(Fore.RED + '[ERRO GIT] O comando falhou.')
        return None

def _get_git_commit_hash(path):
    """Obtém o hash do commit atual no diretório especificado."""
    original_dir = os.getcwd()
    try:
        if os.path.exists(path):
            os.chdir(path)
        hash_output = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        return hash_output if hash_output else 'N/A'
    except Exception:
        return 'N/A'
    finally:
        os.chdir(original_dir)

def _get_detailed_diff_stats(show_code: bool=False, target_path: str=None, cwd: str=None):
    """
    Parser de Estados Estrito (MPoT-1). 
    Garante que metadados do Git não vazem para o relatório semântico.
    """
    from .git import _run_git_command
    num_args = ['diff', '--numstat']
    if target_path:
        num_args.extend(['--', target_path])
    numstat_raw = _run_git_command(num_args, capture_output=True, silent_fail=True, cwd=cwd)
    line_counts = {}
    if numstat_raw:
        for line in numstat_raw.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                added = int(parts[0]) if parts[0].isdigit() else 0
                removed = int(parts[1]) if parts[1].isdigit() else 0
                line_counts[parts[2]] = {'added': added, 'removed': removed}
    diff_args = ['diff', '-U1' if show_code else '-U0', '--no-color']
    if target_path:
        diff_args.extend(['--', target_path])
    diff_raw = _run_git_command(diff_args, capture_output=True, silent_fail=True, cwd=cwd)
    changes = []
    current_file = None
    ln_plus, ln_minus = (0, 0)
    hunk_pattern = re.compile('^@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@')
    func_pattern = re.compile('^[+-]\\s*(?:async\\s+)?def\\s+([a-zA-Z_][a-zA-Z0-9_]*)')
    comment_pattern = re.compile('^([+-])\\s*#\\s*(.*)')
    if diff_raw:
        for line in diff_raw.splitlines():
            if line.startswith('+++ b/'):
                path = line[6:]
                current_file = {'path': path, 'added': line_counts.get(path, {}).get('added', 0), 'removed': line_counts.get(path, {}).get('removed', 0), 'functions': {}, 'comments': [], 'hunks': []}
                changes.append(current_file)
                continue
            if line.startswith(('diff --git', 'index ', '--- a/', 'old mode', 'new mode')):
                continue
            if not current_file:
                continue
            hunk_match = hunk_pattern.match(line)
            if hunk_match:
                ln_minus = int(hunk_match.group(1))
                ln_plus = int(hunk_match.group(2))
                continue
            if line.startswith('+'):
                f_match = func_pattern.match(line)
                if f_match:
                    name = f_match.group(1)
                    current_file['functions'][name] = {'type': '+', 'line': ln_plus}
                c_match = comment_pattern.match(line)
                if c_match:
                    current_file['comments'].append({'text': c_match.group(2).strip(), 'line': ln_plus, 'type': '+'})
                if show_code:
                    current_file['hunks'].append({'line': ln_plus, 'content': line, 'type': 'add'})
                ln_plus += 1
            elif line.startswith('-'):
                f_match = func_pattern.match(line)
                if f_match:
                    name = f_match.group(1)
                    if name in current_file['functions']:
                        current_file['functions'][name]['type'] = '*'
                    else:
                        current_file['functions'][name] = {'type': '-', 'line': ln_minus}
                c_match = comment_pattern.match(line)
                if c_match:
                    current_file['comments'].append({'text': c_match.group(2).strip(), 'line': ln_minus, 'type': '-'})
                if show_code:
                    current_file['hunks'].append({'line': ln_minus, 'content': line, 'type': 'rem'})
                ln_minus += 1
            elif show_code and (not line.startswith('\\')):
                current_file['hunks'].append({'line': ln_plus, 'content': line, 'type': 'ctx'})
                ln_plus += 1
                ln_minus += 1
    for c in changes:
        c['functions'] = [{'name': k, **v} for k, v in c['functions'].items()]
    return changes

def _get_last_commit_info(cwd: str=None):
    """Retorna informações detalhadas do último commit (Chief-Style)."""
    fmt = '%h|%an|%as|%s'
    raw = _run_git_command(['log', '-1', f'--format={fmt}'], capture_output=True, silent_fail=True, cwd=cwd)
    if not raw:
        return None
    parts = raw.strip().split('|')
    if len(parts) < 4:
        return None
    return {'hash': parts[0], 'author': parts[1], 'date': parts[2], 'subject': parts[3]}

def _get_file_history_metadata(path: str, limit: int=10):
    """
    Recupera metadados dos últimos commits que afetaram o arquivo (PASC-1.1).
    """
    fmt = '%h|%as|%an|%s'
    cmd = ['log', f'-{limit}', f'--format={fmt}', '--', path]
    raw = _run_git_command(cmd, capture_output=True, silent_fail=True)
    history = []
    if raw:
        for line in raw.splitlines():
            parts = line.split('|')
            if len(parts) >= 4:
                history.append({'hash': parts[0], 'date': parts[1], 'author': parts[2], 'subject': parts[3]})
    return history

def _get_historical_content(path: str, commit_hash: str) -> str:
    """Recupera o conteúdo de um arquivo em um ponto específico do tempo."""
    return _run_git_command(['show', f'{commit_hash}:{path}'], capture_output=True, silent_fail=True) or ''
    
def _get_line_history(file_path: str, line_num: int) -> dict:
    """Escava a origem de uma linha específica via Git Blame (PASC 8.19)."""
    import subprocess
    import datetime
    
    if not file_path or line_num <= 0: return None
    
    try:
        # porcelain retorna metadados fáceis de parsear
        cmd = ['git', 'blame', '-L', f'{line_num},{line_num}', '--porcelain', file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if res.returncode != 0: return None
        
        lines = res.stdout.splitlines()
        if not lines: return None
        
        info = {
            'hash': lines[0].split()[0],
            'author': 'N/A',
            'date_str': 'N/A',
            'summary': 'N/A'
        }
        
        for ln in lines:
            if ln.startswith('author '): info['author'] = ln[7:].strip()
            if ln.startswith('author-time '): 
                ts = int(ln[12:].strip())
                info['date_str'] = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            if ln.startswith('summary '): info['summary'] = ln[8:].strip()
            
        return info
    except Exception:
        return None
        
def _trace_symbol_death(file_path: str, symbol: str) -> dict:
    """Procura o último commit onde o símbolo foi REMOVIDO (tornando-o órfão)."""
    import subprocess
    try:
        # Busca commits que alteraram a quantidade de ocorrências da string
        # O filtro -S do git detecta mudanças no conteúdo (Pickaxe)
        cmd = ['git', 'log', '-S', symbol, '--pretty=format:%h|%ad|%s', '--date=short', '--', file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if not res.stdout.strip(): return None
        
        # Pegamos o commit mais recente que mexeu no símbolo
        last_change = res.stdout.splitlines()[0]
        h, date, msg = last_change.split('|')
        
        return {'hash': h, 'date': date, 'msg': msg}
    except Exception:
        return None
        
def _get_symbol_attrition(file_path: str, symbol: str) -> list:
    """Busca commits onde a ocorrência do símbolo diminuiu (morte de uso)."""
    import subprocess
    if not symbol or len(symbol) < 2: return []
    
    try:
        # -S do git (Pickaxe) detecta mudanças na quantidade de ocorrências da string
        cmd = ['git', 'log', '-S', symbol, '--pretty=format:%h|%ad|%s', '--date=short', '--', file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        history = []
        if res.stdout.strip():
            for line in res.stdout.splitlines():
                h, date, msg = line.split('|', 2)
                history.append({'hash': h, 'date': date, 'msg': msg})
        
        return history # O primeiro item é a mudança mais recente
    except Exception:
        return []
        
def _get_symbol_attrition_point(file_path: str, symbol: str) -> dict:
    """Escava o histórico em busca do commit de 'morte' e das linhas deletadas."""
    import subprocess
    if not symbol or len(symbol) < 2: return None
    
    try:
        # 1. Busca o commit onde a string mudou (-G detecta mudanças qualitativas)
        cmd_log = ['git', 'log', '-G', symbol, '--pretty=format:%h|%ad|%s', '--date=short', '-n', '1', '--', file_path]
        res_log = subprocess.run(cmd_log, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if not res_log.stdout.strip(): return None
        h, date, msg = res_log.stdout.split('|', 2)
        
        # 2. Extrai o diff de deleção desse commit
        # Usamos -U0 para focar apenas nas linhas alteradas
        cmd_show = ['git', 'show', '-U0', h, '--', file_path]
        res_show = subprocess.run(cmd_show, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        evidence = []
        if res_show.returncode == 0:
            for line in res_show.stdout.splitlines():
                # Captura linhas removidas (-) que não sejam o header do diff
                if line.startswith('-') and not line.startswith('---') and symbol in line:
                    # Se a linha removida for apenas um comentário de remoção do Doxoade, ignoramos
                    if '[DOX-UNUSED]' in line: continue
                    
                    clean_line = line[1:].strip()
                    if clean_line: evidence.append(clean_line)
        
        return {
            'hash': h, 'date': date, 'msg': msg,
            'evidence': evidence[:3] # Top 3 evidências
        }
    except Exception:
        return None
        
def _find_symbol_crime_scene(file_path: str, symbol: str) -> dict:
    """Escava o histórico para achar onde o uso do símbolo foi removido."""
    import subprocess
    if not symbol or len(symbol) < 2: return None
    
    try:
        # 1. Localiza o último commit onde o conteúdo do símbolo mudou (-G)
        cmd_log = ['git', 'log', '-G', symbol, '--pretty=format:%h|%ad|%s', '--date=short', '-n', '1', '--', file_path]
        res_log = subprocess.run(cmd_log, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if not res_log.stdout.strip(): return None
        h, date, msg = res_log.stdout.split('|', 2)
        
        # 2. Extrai o rastro: linhas que foram APAGADAS (-) e que continham o símbolo
        # O parâmetro -U0 garante que pegamos apenas a linha alterada, sem contexto extra.
        cmd_show = ['git', 'show', '-U0', h, '--', file_path]
        res_show = subprocess.run(cmd_show, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        evidence = []
        if res_show.returncode == 0:
            for line in res_show.stdout.splitlines():
                # Captura linhas deletadas que citam o símbolo
                if line.startswith('-') and not line.startswith('---') and symbol in line:
                    clean_line = line[1:].strip()
                    if clean_line: evidence.append(clean_line)
        
        return {
            'hash': h, 'date': date, 'msg': msg,
            'evidence': evidence[:3] # Retorna os 3 principais rastros
        }
    except Exception:
        return None