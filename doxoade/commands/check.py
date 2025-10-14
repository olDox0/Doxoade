# doxoade/commands/check.py
import ast
import os
import sys
import re
from io import StringIO

import click
from colorama import Fore
from pyflakes import api as pyflakes_api

from ..shared_tools import (
    ExecutionLogger,
    _load_config,
    _present_results,
    _get_code_snippet
)

__version__ = "34.0 Alfa"

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fix', is_flag=True, help="Tenta corrigir automaticamente os problemas encontrados.")
@click.option('--ignore-finding', 'ignore_findings_list', multiple=True, help="Ignora um problema específico.")
def check(ctx, path, ignore, format, fix, ignore_findings_list):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Comando extraído para plugin.
    #A função tem como objetivo executar um diagnóstico completo de ambiente e código.
    arguments = ctx.params
    with ExecutionLogger('check', path, arguments) as logger:
        if format == 'text': click.echo(Fore.YELLOW + "[CHECK] Executando 'doxoade check'...")
        config = _load_config()
        final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))
        
        findings_sources = [
            _check_environment(path),
            _check_dependencies(path),
            _check_source_code(path, final_ignore_list, fix_errors=fix, text_format=(format == 'text'))
        ]
        for source in findings_sources:
            for f in source:
                logger.add_finding(f.get('type','info'), f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'), snippet=f.get('snippet'))
        
        critical_errors = 0
        ignored_hashes = set()
        for finding in logger.results.get('findings', []):
            is_ignored = any(ignored_text in finding.get('message', '') for ignored_text in ignore_findings_list)
            if is_ignored:
                ignored_hashes.add(finding.get('hash'))
            elif 'ERROR' in finding.get('type', '').upper():
                critical_errors += 1
        
        _present_results(format, logger.results, ignored_hashes)
        
        if critical_errors > 0:
            sys.exit(1)

def _check_environment(path):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo verificar a consistência do ambiente virtual.
    expected = os.path.abspath(os.path.join(path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python.exe' if os.name == 'nt' else 'python'))
    current = os.path.abspath(sys.executable)
    if current.lower() != expected.lower():
        return [{'type': 'error', 'message': 'Ambiente Inconsistente!', 'details': f'Terminal usa: {current}\n   > Projeto espera: {expected}'}]
    return []

def _check_dependencies(path):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo verificar se dependências críticas estão com versão fixada.
    findings = []
    req_file = os.path.join(path, 'requirements.txt')
    if not os.path.exists(req_file):
        return [{'type': 'warning', 'message': "'requirements.txt' não encontrado."}]
    
    CRITICAL_PACKAGES = ['numpy', 'opencv-python', 'Pillow']
    with open(req_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line_content in enumerate(lines):
        line_num = i + 1
        line = line_content.strip()
        if line and not line.startswith('#'):
            for pkg in CRITICAL_PACKAGES:
                if line.lower().startswith(pkg) and not any(c in line for c in '==<>~'):
                    findings.append({
                        'type': 'warning', 'message': f"Pacote crítico '{pkg}' não tem versão fixada.",
                        'details': "Considere fixar a versão (ex: 'numpy<2.0').",
                        'file': req_file, 'line': line_num,
                        'snippet': {line_num: line}
                    })
    return findings
    
def _check_source_code(path, ignore_list=None, fix_errors=False, text_format=True):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo analisar arquivos .py com Pyflakes e outras heurísticas.
    findings = []
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []

    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))

    unsafe_path_regex = re.compile(r'[^rR]"[a-zA-Z]:\\[^"]*"')

    for file_path in files_to_check:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Pyflakes analysis
        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        
        for line_error in output_stream.getvalue().strip().splitlines():
            try:
                parts = line_error.split(':', 2)
                line_num, message_text = int(parts[1]), parts[2].strip()
                finding = {'type': 'error', 'message': message_text, 'file': file_path, 'line': line_num}
                finding['snippet'] = _get_code_snippet(file_path, line_num)
                findings.append(finding)
            except (IndexError, ValueError):
                continue
        
        if unsafe_path_regex.search(content):
            findings.append({'type': 'warning', 'message': 'Possível caminho de arquivo inseguro (use C:/ ou r"C:\\")', 'file': file_path})
        
        findings.extend(_analyze_regex_risks(content, file_path))

    return findings
    
def _analyze_regex_risks(content, file_path):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo analisar estaticamente padrões de regex em um arquivo.
    findings = []
    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return findings

    regex_functions = {'compile', 'search', 'match', 'fullmatch', 'split', 'findall', 'finditer', 'sub', 'subn'}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                node.func.attr in regex_functions and isinstance(node.func.value, ast.Name) and
                node.func.value.id == 're' and node.args):
            
            pattern_node = node.args[0]
            if isinstance(pattern_node, ast.Constant) and isinstance(pattern_node.value, str):
                try:
                    re.compile(pattern_node.value)
                except re.error as e:
                    findings.append({
                        'type': 'error', 'message': f"Padrão de regex inválido: {e.msg}",
                        'details': f"A expressão '{pattern_node.value}' irá causar um 're.error'.",
                        'file': file_path, 'line': node.lineno,
                        'snippet': _get_code_snippet(file_path, node.lineno)
                    })
    return findings