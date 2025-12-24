# doxoade/commands/check.py
import sys
import os
import json
import click
import hashlib
from pathlib import Path
from colorama import Fore, Style

# Imports da nova arquitetura (Fachada)
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _get_project_config,
    _get_code_snippet, 
    _get_file_hash,
    _present_results, 
    _update_open_incidents,
    _enrich_with_dependency_analysis,
    _enrich_findings_with_solutions,
    _find_project_root
)

# Imports das Sondas (Wrappers)
from ..probes.syntax_probe import analyze as syntax_analyze

# Novo Navegador
from ..dnm import DNM 

# Lógica de Filtros
from .check_filters import filter_and_inject_findings

# --- SISTEMA DE CACHE ---
CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

def _load_cache():
    """Carrega o cache de disco."""
    if not CHECK_CACHE_FILE.is_file(): return {}
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception: return {}

def _save_cache(data):
    """Salva o cache em disco."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception: pass

# --- FUNÇÕES DE SUPORTE ÀS SONDAS ---

def _get_probe_path(probe_name):
    from importlib import resources
    try:
        if hasattr(resources, 'files'):
            return str(resources.files('doxoade.probes').joinpath(probe_name))
        with resources.path('doxoade.probes', probe_name) as p:
            return str(p)
    except Exception:
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _run_probe(probe_file, target_file, python_exe, debug=False, input_data=None):
    """Executor genérico de sondas em subprocesso."""
    import subprocess
    probe_path = _get_probe_path(probe_file)
    
    cmd = [python_exe, probe_path]
    if target_file:
        cmd.append(target_file)
        
    if debug:
        filename = os.path.basename(target_file) if target_file else "STDIN"
        # Use Style.DIM em vez de Fore.DIM
        click.echo(Style.DIM + f"   [DEBUG] Probe '{probe_file}' -> {filename}" + Style.RESET_ALL)

    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result
    except Exception as e:
        if debug: click.echo(Fore.RED + f"   [ERRO PROBE] {e}")
        return None

def _run_syntax_check(f, py_exe, debug):
    res = _run_probe('syntax_probe.py', f, py_exe, debug)
    if res and res.returncode != 0:
        import re
        msg = res.stderr.strip()
        line = 1
        m = re.search(r'(?:line |:)(\d+)(?:[:\n]|$)', msg)
        if m: line = int(m.group(1))
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Erro de Sintaxe: {msg}", 'file': f, 'line': line}]
    return []

def _run_pyflakes_check(f, py_exe, debug):
    res = _run_probe('static_probe.py', f, py_exe, debug)
    findings = []
    if res and res.stdout:
        for line in res.stdout.splitlines():
            # Regex robusto para Windows (C:\...)
            import re
            match = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            
            if match:
                path_str, line_num, msg = match.groups()
                msg = msg.strip()
                cat = 'DEADCODE' if 'unused' in msg else ('RUNTIME-RISK' if 'undefined' in msg else 'STYLE')
                findings.append({
                    'severity': 'WARNING', 
                    'category': cat, 
                    'message': msg, 
                    'file': f, 
                    'line': int(line_num)
                })
    return findings

def _run_hunter_check(f, py_exe, debug):
    res = _run_probe('hunter_probe.py', f, py_exe, debug)
    if res and res.stdout.strip():
        try: 
            # [FIX] Adiciona nome do arquivo e usa Exception específico
            data = json.loads(res.stdout)
            for item in data:
                item['file'] = f
            return data
        except Exception: pass # <--- CORRIGIDO AQUI
    return []

def _run_style_check(f, py_exe, debug):
    payload = json.dumps({'files': [f], 'comments_only': False})
    res = _run_probe('style_probe.py', None, py_exe, debug, input_data=payload)
    if res and res.stdout.strip():
        try: return json.loads(res.stdout)
        except Exception: pass # <--- CORRIGIDO AQUI
    return []

def _run_clone_check(files, py_exe, debug):
    if len(files) < 2: return []
    if debug: click.echo(Fore.CYAN + f"   [DEBUG] Iniciando análise de clones em {len(files)} arquivos...")
    
    payload = json.dumps(files)
    res = _run_probe('clone_probe.py', None, py_exe, debug, input_data=payload)
    if res and res.stdout.strip():
        try: return json.loads(res.stdout)
        except Exception: pass # <--- CORRIGIDO AQUI
    return []

# --- LÓGICA PRINCIPAL ---

def run_check_logic(path, ignore, fix, debug, fast, no_imports, no_cache, target_files, clones, continue_on_error, exclude_categories):
    cache = {} if no_cache else _load_cache()
    
    # 1. Resolução Inteligente de Caminho e Raiz
    abs_input_path = os.path.abspath(path)
    
    # Se o usuário passou um arquivo, a raiz do projeto não é o arquivo, 
    # mas sim o diretório do projeto acima dele.
    if os.path.isfile(abs_input_path):
        root_path = _find_project_root(abs_input_path)
        # Força o arquivo específico como alvo
        if target_files is None:
            target_files = [abs_input_path]
    else:
        # Se é diretório, usa ele como raiz (ou busca a raiz real a partir dele)
        root_path = os.path.abspath(path)

    # 2. Coleta de Arquivos (DNM ou Alvo Específico)
    if target_files:
        files = [os.path.abspath(f) for f in target_files]
        if debug: 
            click.echo(f"[DEBUG] Modo Arquivo Único/Lista.")
            click.echo(f"[DEBUG] Raiz do Projeto detectada: {root_path}")
            click.echo(f"[DEBUG] Alvos: {[os.path.basename(f) for f in files]}")
    else:
        if debug: click.echo(f"[DEBUG] Iniciando DNM em {root_path}...")
        dnm = DNM(root_path)
        files = dnm.scan(extensions=['.py'])
        if debug: click.echo(f"[DEBUG] DNM encontrou {len(files)} arquivos.")

    if not files:
        return {'summary': {}, 'findings': []}

    python_exe = _get_venv_python_executable() or sys.executable
    raw_findings = []

    # 2. Execução das Sondas (Fase Individual) com Cache Inteligente
    files_to_scan = []
    
    for fp in files:
        try:
            stat = os.stat(fp)
            mtime = stat.st_mtime
            size = stat.st_size
            
            if size == 0: continue

            rel = os.path.relpath(fp, root_path)
            cached_data = cache.get(rel)
            
            hit = False
            if not no_cache and cached_data:
                # Verifica se data e tamanho são idênticos
                if cached_data.get('mtime') == mtime and cached_data.get('size') == size:
                    hit = True
                # Fallback legado
                elif 'mtime' not in cached_data and cached_data.get('hash') == _get_file_hash(fp):
                    hit = True

            if hit:
                if debug: click.echo(Fore.GREEN + f"[CACHE] {rel}")
                
                # [FIX] Cura do Cache: Recupera findings e re-injeta o nome do arquivo
                cached_findings = cached_data.get('findings', [])
                for cf in cached_findings:
                    # Se o finding veio do cache sem nome de arquivo (legado), conserta agora
                    if not cf.get('file'):
                        cf['file'] = fp
                
                raw_findings.extend(cached_findings)
                
                # Atualiza metadados do cache
                cache[rel]['mtime'] = mtime
                cache[rel]['size'] = size
            else:
                files_to_scan.append((fp, rel, mtime, size))
                
        except OSError:
            continue

    if debug and files_to_scan:
        click.echo(Fore.YELLOW + f"[DEBUG] Processando {len(files_to_scan)} arquivos alterados...")

    # Processa apenas o delta
    if files_to_scan:
        with click.progressbar(files_to_scan, label='Analisa', show_pos=True) as bar:
            for fp, rel, mtime, size in bar:
                # A. SINTAXE
                syn = _run_syntax_check(fp, python_exe, debug)
                if syn:
                    raw_findings.extend(syn)
                    if not continue_on_error: continue 
                
                # B. SONDAS
                pf = _run_pyflakes_check(fp, python_exe, debug)
                ht = _run_hunter_check(fp, python_exe, debug)
                st = _run_style_check(fp, python_exe, debug)
                
                new_findings = pf + ht + st
                raw_findings.extend(new_findings)
                
                # Atualiza Cache
                file_hash = _get_file_hash(fp)
                cache[rel] = {
                    'hash': file_hash,
                    'mtime': mtime,
                    'size': size,
                    'findings': new_findings
                }

    # 3. Execução das Sondas Globais (Clones)
    if clones:
        if debug: click.echo("[DEBUG] Rodando análise de clones...")
        raw_findings.extend(_run_clone_check(files, python_exe, debug))
    elif not fast:
        # Se não é fast, roda clones (comportamento padrão)
        raw_findings.extend(_run_clone_check(files, python_exe, debug))

    # 4. Enriquecimento
    if not fast:
        if debug: click.echo("[DEBUG] Abdução...")
        _enrich_with_dependency_analysis(raw_findings, root_path)
    
    _enrich_findings_with_solutions(raw_findings)

    # 5. Filtragem e Priorização
    if exclude_categories is None: exclude_categories = []
    config = _get_project_config(None, start_path=path)
    toml_excludes = config.get('exclude_categories', [])
    final_exclude_cats = set([c.upper() for c in exclude_categories] + [c.upper() for c in toml_excludes])
    
    STYLE_GROUP = {'STYLE', 'COMPLEXITY', 'ROBUSTNESS', 'DOCS', 'GLOBAL-STATE', 'RECURSION'}

    findings_by_file = {}
    for f in raw_findings:
        p = f.get('file')
        if p not in findings_by_file: findings_by_file[p] = []
        findings_by_file[p].append(f)
        
    processed_findings = []
    all_files_set = set(files) | set(findings_by_file.keys())
    
    for fp in all_files_set:
        fs = findings_by_file.get(fp, [])
        processed_findings.extend(filter_and_inject_findings(fs, fp))

    final_findings = []
    for f in processed_findings:
        cat = f.get('category', '').upper()
        
        # Nunca filtra Críticos
        if cat in ['SECURITY', 'CRITICAL', 'SYNTAX', 'RISK-MUTABLE']:
            final_findings.append(f)
            continue
            
        if 'STYLE' in final_exclude_cats and cat in STYLE_GROUP: continue
        if cat in final_exclude_cats: continue
        final_findings.append(f)

    # Ordenação por Prioridade
    PRIORITY_MAP = {
        'SECURITY': 0, 'CRITICAL': 0, 'SYNTAX': 0,
        'ERROR': 1, 'RISK-MUTABLE': 1, 'BROKEN-LINK': 1,
        'WARNING': 2, 'RUNTIME-RISK': 2, 'DEPENDENCY': 2, 'DUPLICATION': 2,
        'INFO': 3, 'QA-REMINDER': 3, 'DEADCODE': 3,
        'STYLE': 4, 'COMPLEXITY': 4, 'DOCS': 4, 'ROBUSTNESS': 4, 'RECURSION': 4
    }

    def get_prio(item):
        cat = item.get('category', '').upper()
        sev = item.get('severity', '').upper()
        base = PRIORITY_MAP.get(cat, 5)
        if base == 5 and sev == 'CRITICAL': base = 0
        return base

    final_findings.sort(key=lambda x: (get_prio(x), x.get('file', ''), x.get('line') or 0))

    results = {
        'summary': {'critical': 0, 'errors': 0, 'warnings': 0, 'info': 0},
        'findings': []
    }
    
    # 6. Exibição e Logging
    with ExecutionLogger('check', path, {'fix': fix}) as logger:
        for f in final_findings:
            s = _get_code_snippet(f.get('file'), f.get('line'))
            logger.add_finding(
                severity=f['severity'],
                message=f['message'],
                category=f.get('category', 'UNCATEGORIZED'),
                file=f.get('file'),
                line=f.get('line'),
                snippet=s,
                finding_hash=f.get('hash'),
                suggestion_content=f.get('suggestion_content'),
                suggestion_line=f.get('suggestion_line'),
                suggestion_source=f.get('suggestion_source'),
                suggestion_action=f.get('suggestion_action'),
                import_suggestion=f.get('import_suggestion')
            )
        
        if not no_cache: _save_cache(cache)
        return logger.results

@click.command('check')
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas automaticamente.")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração detalhada.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fast', is_flag=True, help="Executa uma análise rápida.")
@click.option('--no-imports', is_flag=True, help="Pula verificação de imports.")
@click.option('--no-cache', is_flag=True, help="Força reanálise completa.")
@click.option('--clones', is_flag=True, help="Força análise de clones.")
@click.option('--continue-on-error', '-C', is_flag=True, help="Continua após erros de sintaxe.")
@click.option('--exclude', '-x', multiple=True, help="Categorias para ignorar.")
def check(path, ignore, fix, debug, output_format, fast, no_imports, no_cache, clones, continue_on_error, exclude):
    """Análise estática, estrutural e de duplicatas completa."""
    if not debug and output_format == 'text':
        click.echo(Fore.YELLOW + "[CHECK] Executando análise...")

    results = run_check_logic(
        path, ignore, fix, debug, fast, no_imports, no_cache, None, clones, continue_on_error, exclude
    )
    
    _update_open_incidents(results, os.path.abspath(path))
    
    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not debug:
            _present_results('text', results)
            
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)

if __name__ == "__main__":
    check()