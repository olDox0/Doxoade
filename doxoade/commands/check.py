# -*- coding: utf-8 -*-
"""
Módulo Auditor Mestre (Check) - v38.8 Gold.
Orquestra o pipeline de análise estática e estrutural.
FIX: Removido import circular de _run_clone_check e corrigido filtro de pasta.
"""

import sys
import os
import json
import click
import sqlite3
import subprocess
import logging
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from colorama import Fore
from radon.visitors import ComplexityVisitor

# Imports Core (Apenas o que é externo)
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _get_code_snippet, 
    _get_file_hash,
    _present_results, 
    _update_open_incidents,
    _enrich_with_dependency_analysis,
    _enrich_findings_with_solutions,
    _find_project_root
)
from ..dnm import DNM 
from .check_filters import filter_and_inject_findings
from ..fixer import AutoFixer
from ..database import get_db_connection
from ..probes.manager import ProbeManager

__version__ = "38.8 Alfa (Gold-Standard-Fixed)"

# --- CONFIGURAÇÃO E CACHE ---
CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

def _load_cache() -> Dict[str, Any]:
    """Carrega o cache de análise do disco."""
    if not CHECK_CACHE_FILE.is_file():
        return {}
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_cache(data: Dict[str, Any]) -> None:
    """Persiste o cache no disco."""
    if data is None:
        return
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logging.error(f"Falha ao salvar cache: {e}")

# --- ORQUESTRAÇÃO DE SONDAS ---

def _get_probe_path(probe_name: str) -> str:
    """Localiza o script da sonda de forma robusta."""
    from importlib import resources
    try:
        if hasattr(resources, 'files'):
            return str(resources.files('doxoade.probes').joinpath(probe_name))
        with resources.path('doxoade.probes', probe_name) as p:
            return str(p)
    except (ImportError, AttributeError, FileNotFoundError):
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _run_probe(probe_file: str, target_file: Optional[str], python_exe: str, 
               input_data: Optional[str] = None) -> subprocess.CompletedProcess:
    """Executor de sonda (Aegis)."""
    if not python_exe:
        raise ValueError("Interpretador Python não configurado.")

    cmd = [python_exe, _get_probe_path(probe_file)]
    if target_file:
        cmd.append(target_file)

    try:
        return subprocess.run(
            cmd, input=input_data, capture_output=True,
            text=True, encoding='utf-8', errors='replace', shell=False # nosec
        )
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))

# --- ANALISADORES (DEFINIÇÕES LOCAIS) ---

def _run_probe_via_manager(manager: ProbeManager, probe_name: str, target_file: Optional[str], 
                          payload: Optional[Dict[str, Any]] = None):
    """Encapsula a execução via Manager no pipeline do Check."""
    probe_path = _get_probe_path(probe_name)
    result = manager.execute(probe_path, target_file, payload)
    
    if not result["success"]:
        # Se falhou, registramos como erro de infraestrutura
        logging.error(f"Sonda {probe_name} falhou: {result['error']}")
        return result["stdout"], result["error"], False
    
    return result["stdout"], None, True

# 1. Ajuste os Analisadores para usar o Manager
def _run_syntax_check(f: str, manager: ProbeManager) -> List[Dict[str, Any]]:
    res = manager.execute(_get_probe_path('syntax_probe.py'), f)
    if not res["success"]:
        msg = res["error"]
        m = re.search(r'(?:line |:)(\d+)', msg)
        line = int(m.group(1)) if m else 1
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Sintaxe Inválida: {msg}", 'file': f, 'line': line}]
    return []

def _run_pyflakes_check(f: str, manager: ProbeManager) -> List[Dict[str, Any]]:
    res = manager.execute(_get_probe_path('static_probe.py'), f)
    findings = []
    if res["stdout"]:
        for line in res["stdout"].splitlines():
            match = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            if match:
                _, line_num, msg = match.groups()
                cat = 'DEADCODE' if 'unused' in msg.lower() else ('RUNTIME-RISK' if 'undefined' in msg.lower() else 'STYLE')
                findings.append({'severity': 'WARNING', 'category': cat, 'message': msg.strip(), 'file': f, 'line': int(line_num)})
    return findings

def _run_json_probe(probe_name: str, f: str, manager: ProbeManager) -> List[Dict[str, Any]]:
    # Hunter e Style usam JSON
    payload = {'files': [f], 'comments_only': False} if "style" in probe_name else None
    res = manager.execute(_get_probe_path(probe_name), f if not payload else None, payload=payload)
    if res["stdout"].strip():
        try:
            data = json.loads(res["stdout"])
            if isinstance(data, list):
                for d in data: d['file'] = f
                return data
            data['file'] = f
            return [data]
        except: pass
    return []

# 2. O CORAÇÃO DO ERRO: Ajuste a definição de process_single_file
def _process_single_file(item: tuple, manager: ProbeManager, continue_on_error: bool, cache: dict) -> List[Dict[str, Any]]:
    """Executa a bateria de sondas usando o manager blindado."""
    fp, rel, mtime, size = item
    
    # Executa pipeline
    findings = _run_syntax_check(fp, manager)
    if findings and not continue_on_error:
        return findings
        
    findings.extend(_run_pyflakes_check(fp, manager))
    findings.extend(_run_json_probe('hunter_probe.py', fp, manager))
    findings.extend(_run_style_check(fp)) # Style check é local/AST, não precisa de manager
    
    # Atualiza cache
    cache[rel] = {'hash': _get_file_hash(fp), 'mtime': mtime, 'size': size, 'findings': findings}
    return findings

def run_check_logic(path: str, fix: bool, fast: bool, no_cache: bool, 
                    clones: bool, continue_on_error: bool, exclude_categories: Optional[List[str]] = None,
                    target_files: Optional[List[str]] = None):
    """Orquestrador Master com filtragem de diretório."""
    abs_input_path = os.path.abspath(path)
    project_root = _find_project_root(abs_input_path)
    dnm = DNM(project_root)
    cache = {} if no_cache else _load_cache()
    python_exe = _get_venv_python_executable() or sys.executable
    manager = ProbeManager(python_exe, project_root) # Instancia uma vez
    
    # Seleção de Alvos
    if target_files:
        # Se os arquivos foram passados explicitamente, confiamos no chamador.
        # Removemos o filtro 'if not dnm.is_ignored' daqui.
        files = [os.path.abspath(f) for f in target_files]
    elif os.path.isfile(abs_input_path):
        files = [abs_input_path]
    else:
        # Modo diretório: aqui sim o DNM manda.
        all_project_files = dnm.scan(extensions=['.py'])
        files = [f for f in all_project_files if os.path.abspath(f).startswith(abs_input_path)]

    if not files:
        # Adicione este log para debug interno se necessário
        # logging.debug("Nenhum arquivo selecionado para análise.")
        return {'summary': {'errors': 0, 'warnings': 0}, 'findings': []}


    raw_findings, files_to_scan = [], []

    for fp in files:
        rel = os.path.relpath(fp, project_root).replace('\\', '/')
        try:
            st = os.stat(fp)
            # --- BLINDAGEM DE CACHE (Resiliência v69.1) ---
            if not no_cache and rel in cache:
                c = cache[rel]
                
                # MPoT-7: Validação defensiva de chaves do dicionário externo
                mtime_cached = c.get('mtime')
                size_cached = c.get('size')
                findings_cached = c.get('findings')

                # Só considera "Hit" se todas as métricas existirem e baterem
                if all(v is not None for v in [mtime_cached, size_cached, findings_cached]):
                    if abs(mtime_cached - st.st_mtime) < 0.0001 and size_cached == st.st_size:
                        for f in findings_cached: 
                            f['file'] = fp
                        raw_findings.extend(findings_cached)
                        continue
            
            # Se chegou aqui, é um "Cache Miss" ou Cache Inválido
            files_to_scan.append((fp, rel, st.st_mtime, st.st_size))
        except OSError: 
            continue

    # --- FASE 1: ANÁLISE INDIVIDUAL (Já operacional) ---
    if files_to_scan:
        with click.progressbar(files_to_scan, label='Analisando') as bar:
            for item in bar:
                raw_findings.extend(_process_single_file(item, manager, continue_on_error, cache))

    # --- FASE 2: ANÁLISE ESTRUTURAL (PROBES DE ELITE) ---
    if not fast:
        def canonical(p): return os.path.abspath(p).replace('\\', '/').lower()
        c_files = [canonical(f) for f in files]
        c_root = canonical(project_root)
        
        # Payload unificado para todas as sondas de elite
        ctx_payload = {"files": c_files, "project_root": c_root}
        
        # Lista de sondas para execução em lote
        structural_probes = [
            ('clone_probe.py', 'Clones'),
            ('orphan_probe.py', 'Órfãos'),
            ('xref_probe.py', 'XREF')
        ]

        for probe_file, label in structural_probes:
            # XREF precisa do root no argv[1] por design legado, os outros não.
            target = c_root if probe_file == 'xref_probe.py' else None
            
            res = manager.execute(_get_probe_path(probe_file), target_file=target, payload=ctx_payload)
            
            if res["success"] and res["stdout"]:
                try:
                    data = json.loads(res["stdout"])
                    for d in data: 
                        if 'file' in d: d['file'] = os.path.normpath(d['file'])
                    raw_findings.extend(data)
                except Exception as e:
                    logging.error(f"Erro ao processar {label}: {e}")

    # --- FASE 3: ENRIQUECIMENTO ---
    # Garante que as descobertas sejam enriquecidas antes de ir para o Logger
    _enrich_findings_with_solutions(raw_findings, project_root)

    if fix:
        with ExecutionLogger('autofix', project_root, {}) as f_log:
            fixer = AutoFixer(f_log)
            conn = get_db_connection()
            templates = conn.execute("SELECT * FROM solution_templates WHERE confidence > 0").fetchall()
            for f in sorted(raw_findings, key=lambda x: x.get('line', 0), reverse=True):
                match = _match_finding_to_template(f, templates)
                if match['type']:
                    fixer.apply_fix(os.path.abspath(f['file']), f['line'], match['type'], match['context'])
            conn.close()
            cache = {}

    with ExecutionLogger('check', project_root, {'fix': fix}) as logger:
        _log_check_results(raw_findings, project_root, exclude_categories, logger)
        if not no_cache: _save_cache(cache)
        return logger.results

def _run_style_check(f: str) -> List[Dict[str, Any]]:
    """Calcula complexidade real via Radon e valida MPoT."""
    findings = []
    try:
        with open(f, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            tree = ast.parse(content)
            v = ComplexityVisitor.from_ast(tree)
            for func in v.functions:
                if func.complexity > 10:
                    findings.append({
                        'severity': 'WARNING', 'category': 'COMPLEXITY',
                        'message': f"Função '{func.name}' é complexa (CC: {func.complexity}). Refatore.",
                        'file': f, 'line': func.lineno
                    })
    except Exception: pass
    return findings

def _run_clone_check(files: List[str], py_exe: str) -> List[Dict[str, Any]]:
    """Detecta duplicação de lógica (DRY)."""
    if len(files) < 2: return []
    payload = json.dumps(files)
    res = _run_probe('clone_probe.py', None, py_exe, input_data=payload)
    if res.stdout.strip():
        try: return json.loads(res.stdout)
        except json.JSONDecodeError: pass
    return []

# --- PIPELINE E FILTRAGEM ---

def _match_finding_to_template(finding: Dict[str, Any], templates: List[sqlite3.Row]) -> Dict[str, Any]:
    """MPoT-7: Retorno consistente."""
    msg, category = finding.get('message', ''), finding.get('category', '')
    result = {'type': None, 'context': {}}
    if "except:" in msg.lower() and "genérico" in msg.lower():
        return {'type': 'FIX_BARE_EXCEPT', 'context': {}}
    for t in templates:
        if t['category'] != category: continue
        pattern = (re.escape(t['problem_pattern']).replace('<MODULE>', '(.+?)').replace('<VAR>', '(.+?)').replace('<LINE>', r'(\d+)'))
        match = re.fullmatch(pattern, msg)
        if match:
            result['type'] = t['solution_template']
            if match.groups(): result['context']['var_name'] = match.group(1)
            return result
    return result

def _log_check_results(raw_findings: List[Dict[str, Any]], project_root: str, 
                      exclude_categories: Optional[List[str]], logger: ExecutionLogger) -> None:
    """Filtra e registra achados, incluindo sugestões da Gênese."""
    if not raw_findings: return
    
    processed = filter_and_inject_findings(raw_findings, project_root)
    excludes = set([c.upper() for c in (exclude_categories or [])])
    
    for f in processed:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat in excludes: continue
        
        # Garante caminho absoluto para leitura do snippet e relativo para exibição
        abs_file = os.path.abspath(f['file'])
        rel_file = os.path.relpath(abs_file, project_root)
        
        # --- FIX: Passagem de TODOS os campos para o Logger ---
        logger.add_finding(
            severity=f['severity'], 
            message=f['message'], 
            category=cat,
            file=rel_file, 
            line=f.get('line', 0), 
            snippet=_get_code_snippet(abs_file, f.get('line')),
            finding_hash=f.get('hash'),
            # Dados da Gênese (Fundamentais para exibir sugestões)
            import_suggestion=f.get('import_suggestion'),
            suggestion_content=f.get('suggestion_content'),
            suggestion_line=f.get('suggestion_line'),
            suggestion_source=f.get('suggestion_source'),
            suggestion_action=f.get('suggestion_action')
        )

@click.command('check')
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--fix', is_flag=True, help="Corrige problemas.")
@click.option('--debug', is_flag=True, help="Saída detalhada.")
@click.option('--format', 'out_fmt', type=click.Choice(['text', 'json']), default='text')
@click.option('--ignore', multiple=True, help="Ignora pastas.")
@click.option('--fast', is_flag=True, help="Pula análises pesadas.")
@click.option('--no-cache', is_flag=True, help="Força reanálise.")
@click.option('--clones', is_flag=True, help="Análise DRY.")
@click.option('--continue-on-error', '-C', is_flag=True, help="Ignora erros de sintaxe.")
@click.option('--exclude', '-x', multiple=True, help="Categorias ignoradas.")
def check(path, **kwargs):
    """Análise completa de qualidade e segurança."""
    if kwargs.get('out_fmt') == 'text' and not kwargs.get('debug'):
        click.echo(Fore.YELLOW + "[CHECK] Executando auditoria...")

    results = run_check_logic(
        path, kwargs.get('fix'), kwargs.get('fast'), kwargs.get('no_cache'), 
        kwargs.get('clones'), kwargs.get('continue_on_error'), kwargs.get('exclude')
    )
    _update_open_incidents(results, os.path.abspath(path))
    if kwargs.get('out_fmt') == 'json': print(json.dumps(results, indent=2, ensure_ascii=False))
    else: _present_results('text', results)
    if results.get('summary', {}).get('critical', 0) > 0: sys.exit(1)

# doxoade/probes/xref_probe.py

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("[]"); sys.exit(0)
            
        project_root = sys.argv[1] # Recebe o target_file do manager
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print("[]"); sys.exit(0)
            
        data = json.loads(raw_input)
        # Extrai a lista de arquivos do dicionário unificado
        files = data.get("files", []) if isinstance(data, dict) else data
    except exception as e:
        logging.error(f" Ocorrencia no __main__ do check:{e}")
        logging.error(f"     raw_findings: {raw_findings}")
        logging.error(f"     project_root: {project_root}")
        logging.error(f"     data: {data}")
        logging.error(f"     files: {files}")