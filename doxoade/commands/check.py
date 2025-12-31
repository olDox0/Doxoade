# -*- coding: utf-8 -*-
"""
Módulo Auditor Mestre (Check) - Versão de Ouro.
Pipeline: Sintaxe -> Pyflakes -> Hunter -> Style -> DRY -> Autofix.
Evolução: Recuperação de parsing específico para sondas de texto (Pyflakes).
"""

import sys
import os
import json
import click
import sqlite3
import subprocess # nosec
import logging
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from colorama import Fore

# Imports Core
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
from radon.visitors import ComplexityVisitor

__version__ = "38.5 Alfa (Gold Standard - Final)"

# --- CONFIGURAÇÃO E CACHE ---
CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

def _load_cache() -> Dict[str, Any]:
    """Carrega o cache do disco. MPoT-7: Retorno consistente."""
    if not CHECK_CACHE_FILE.is_file():
        return {}
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_cache(data: Dict[str, Any]) -> None:
    """Persiste o cache. MPoT-5: Validação de entrada."""
    if data is None:
        return
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logging.error(f"Falha ao salvar cache: {e}")

# --- ORQUESTRAÇÃO DE SONDAS (AEGIS) ---

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
    """Executor de sonda (Protocolo Aegis)."""
    if not python_exe:
        raise ValueError("Python não configurado.")

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

# --- ANALISADORES (RESOLUÇÃO DE REGRESSÃO) ---

def _run_syntax_check(f: str, py_exe: str) -> List[Dict[str, Any]]:
    """Verifica erros de sintaxe (Fail-Fast)."""
    res = _run_probe('syntax_probe.py', f, py_exe)
    if res.returncode != 0:
        msg = res.stderr.strip()
        m = re.search(r'(?:line |:)(\d+)(?:[:\n]|$)', msg)
        line = int(m.group(1)) if m else 1
        return [{'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Erro: {msg}", 'file': f, 'line': line}]
    return []

def _run_pyflakes_check(f: str, py_exe: str) -> List[Dict[str, Any]]:
    """Linter Pyflakes (Parser de Texto)."""
    res = _run_probe('static_probe.py', f, py_exe)
    findings = []
    if res.stdout:
        for line in res.stdout.splitlines():
            match = re.match(r'^(.+):(\d+):(?:\d+):? (.+)$', line)
            if match:
                _, line_num, msg = match.groups()
                cat = 'DEADCODE' if 'unused' in msg.lower() else ('RUNTIME-RISK' if 'undefined' in msg.lower() else 'STYLE')
                findings.append({'severity': 'WARNING', 'category': cat, 'message': msg.strip(), 'file': f, 'line': int(line_num)})
    return findings

def _run_json_probe(probe: str, f: str, py_exe: str) -> List[Dict[str, Any]]:
    """Executa sondas que retornam JSON (Hunter, Style)."""
    payload = json.dumps({'files': [f], 'comments_only': False}) if "style" in probe else None
    res = _run_probe(probe, f if not payload else None, py_exe, input_data=payload)
    if res.stdout.strip():
        try:
            data = json.loads(res.stdout)
            if isinstance(data, list):
                for d in data: d['file'] = f
                return data
            data['file'] = f
            return [data]
        except json.JSONDecodeError: pass
    return []

def _run_style_check(f: str) -> List[Dict[str, Any]]: # FIX: Removido py_exe não utilizado
    """Valida conformidade MPoT e calcula complexidade via Radon."""
    findings = []
    try:
        with open(f, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            tree = ast.parse(content)
            # Complexidade Radon
            from radon.visitors import ComplexityVisitor
            v = ComplexityVisitor.from_ast(tree)
            for func in v.functions:
                if func.complexity > 10:
                    findings.append({
                        'severity': 'WARNING', 'category': 'COMPLEXITY',
                        'message': f"Função '{func.name}' complexa (CC: {func.complexity}).",
                        'file': f, 'line': func.lineno
                    })
    except Exception: pass
    return findings

# --- MOTOR DE CORREÇÃO (AUTOFIX) ---

def _match_finding_to_template(finding: Dict[str, Any], templates: List[sqlite3.Row]) -> Dict[str, Any]:
    """MPoT-7: Match estruturado de templates."""
    msg, category = finding.get('message', ''), finding.get('category', '')
    result = {'type': None, 'context': {}}

    if "except:" in msg.lower() and "genérico" in msg.lower():
        return {'type': 'FIX_BARE_EXCEPT', 'context': {}}

    for t in templates:
        if t['category'] != category: continue
        pattern = (re.escape(t['problem_pattern'])
            .replace('<MODULE>', '(.+?)').replace('<VAR>', '(.+?)').replace('<LINE>', r'(\d+)'))
        match = re.fullmatch(pattern, msg)
        if match:
            result['type'] = t['solution_template']
            if match.groups(): result['context']['var_name'] = match.group(1)
            return result
    return result

# --- LOGGING E PIPELINE ---

def _log_check_results(raw_findings: List[Dict[str, Any]], project_root: str, 
                      exclude_categories: Optional[List[str]], logger: ExecutionLogger) -> None:
    """
    Filtra, injeta TODOs e registra os achados no logger final.
    CORREÇÃO: Agrupa por arquivo para permitir que o filtro leia o código fonte e processe # noqa.
    """
    if logger is None or raw_findings is None:
        raise ValueError("Logger e achados são obrigatórios.")

    # 1. Agrupar findings por arquivo
    findings_by_file = {}
    for f in raw_findings:
        file_path = f.get('file')
        if not file_path: continue
        # Usa o caminho absoluto como chave para evitar confusão entre relativo/absoluto
        abs_p = os.path.abspath(file_path)
        if abs_p not in findings_by_file:
            findings_by_file[abs_p] = []
        findings_by_file[abs_p].append(f)

    excludes = set([c.upper() for c in (exclude_categories or [])])
    
    # 2. Processar cada arquivo individualmente no filtro
    for abs_file_path, findings in findings_by_file.items():
        # Agora o filtro recebe o arquivo correto para ler as linhas e achar o # noqa
        processed = filter_and_inject_findings(findings, abs_file_path)
        
        for f in processed:
            cat = f.get('category', 'UNCATEGORIZED').upper()
            if cat in excludes: 
                continue
            
            # Normaliza para exibição relativa ao projeto
            rel_file = os.path.relpath(abs_file_path, project_root)
            
            logger.add_finding(
                severity=f['severity'], 
                message=f['message'], 
                category=cat,
                file=rel_file, 
                line=f.get('line', 0), 
                snippet=_get_code_snippet(abs_file_path, f.get('line')),
                finding_hash=f.get('hash'), 
                import_suggestion=f.get('import_suggestion')
            )

def _process_single_file(item: tuple, python_exe: str, continue_on_error: bool, cache: dict) -> List[Dict[str, Any]]:
    """Pipeline por arquivo com cálculo de complexidade real."""
    fp, rel, mtime, size = item
    findings = _run_syntax_check(fp, python_exe)
    if findings and not continue_on_error: return findings

    # 1. Pyflakes (Texto)
    findings.extend(_run_pyflakes_check(fp, python_exe))
    
    # 2. Sondas JSON (Hunter, Style)
    for probe in ['hunter_probe.py', 'style_probe.py']:
        findings.extend(_run_json_probe(probe, fp, python_exe))

    # 3. Complexidade via Radon (In-Process para performance)
    try:
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
            v = ComplexityVisitor.from_ast(ast.parse(code))
            for func in v.functions:
                # Adiciona metadado de complexidade para o deepcheck ler depois
                # e gera aviso se for muito alta (> 10)
                if func.complexity > 10:
                    findings.append({
                        'severity': 'WARNING', 'category': 'COMPLEXITY',
                        'message': f"Função '{func.name}' é complexa (CC: {func.complexity}). Refatore.",
                        'file': fp, 'line': func.lineno
                    })
    except Exception: pass
    
    cache[rel] = {'hash': _get_file_hash(fp), 'mtime': mtime, 'size': size, 'findings': findings}
    return findings

def run_check_logic(path: str, fix: bool, fast: bool, no_cache: bool, 
                    clones: bool, continue_on_error: bool, 
                    exclude_categories: Optional[List[str]] = None,
                    target_files: Optional[List[str]] = None):
    """
    Orquestrador Master.
    FIX: Agora filtra 'target_files' usando as regras de ignore do DNM.
    """
    project_root = _find_project_root(os.path.abspath(path))
    cache = {} if no_cache else _load_cache()
    dnm = DNM(project_root) # Instancia o navegador que lê o TOML
    
    # --- Lógica de Seleção Filtrada ---
    if target_files:
        # Só analisa se o arquivo não estiver na lista de ignore do TOML
        files = [
            os.path.abspath(f) for f in target_files 
            if not dnm.is_ignored(Path(f))
        ]
    elif os.path.isfile(os.path.abspath(path)):
        files = [os.path.abspath(path)]
    else:
        files = dnm.scan(extensions=['.py'])
    # ----------------------------------

    if not files: 
        return {'summary': {'errors': 0, 'warnings': 0}, 'findings': []}

    # ... (Resto da lógica de processamento permanece a mesma)
    # --------------------------------------

    python_exe = _get_venv_python_executable() or sys.executable
    raw_findings, files_to_scan = [], []

    for fp in files:
        rel = os.path.relpath(fp, project_root).replace('\\', '/')
        try:
            st = os.stat(fp)
            if not no_cache and rel in cache:
                c = cache[rel]
                if abs(c['mtime'] - st.st_mtime) < 0.0001 and c['size'] == st.st_size:
                    for f in c['findings']: f['file'] = rel
                    raw_findings.extend(c['findings'])
                    continue
            files_to_scan.append((fp, rel, st.st_mtime, st.st_size))
        except OSError: continue

    if files_to_scan:
        with click.progressbar(files_to_scan, label='Analisando') as bar:
            for item in bar:
                raw_findings.extend(_process_single_file(item, python_exe, continue_on_error, cache))

    if clones or not fast:
        payload = json.dumps(files)
        res = _run_probe('clone_probe.py', None, python_exe, input_data=payload)
        if res.stdout.strip():
            try: raw_findings.extend(json.loads(res.stdout))
            except json.JSONDecodeError: pass

    if not fast: _enrich_with_dependency_analysis(raw_findings, project_root)
    _enrich_findings_with_solutions(raw_findings)

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

if __name__ == "__main__":
    check()