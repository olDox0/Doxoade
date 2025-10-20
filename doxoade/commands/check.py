# doxoade/commands/check.py
import sys
import re
import os
import importlib.util
import click
import ast
from pyflakes import api as pyflakes_api
from io import StringIO
#from colorama import Fore

from ..shared_tools import ExecutionLogger, _present_results, _get_code_snippet
#_load_config,

__version__ = "34.0 Alfa"


@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text')
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas (não implementado).")
@click.option('--ignore-finding', 'ignore_findings_list', multiple=True, help="Ignora um problema específico.")
def check(ctx, path, ignore, format, fix, ignore_findings_list):
    """Análise estática completa do projeto."""
    arguments = ctx.params
    with ExecutionLogger('check', path, arguments) as logger:
        # (O corpo principal da função 'check' permanece o mesmo,
        # ele apenas orquestra as chamadas para as funções acima)
        if format == 'text': click.echo("[CHECK] Executando análise de integridade do projeto...")
        
        # (Removido _check_environment)
        findings_sources = [
            _check_dependencies(path),
            _check_source_code(path, list(ignore))
        ]
        
        for source in findings_sources:
            for f in source:
                logger.add_finding(f.get('type','info'), f['message'], file=f.get('file'), line=f.get('line'), snippet=f.get('snippet'))
        
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

def _check_dependencies(path):
    """Verifica se dependências críticas estão com versão fixada."""
    findings = []
    req_file = os.path.join(path, 'requirements.txt')
    if not os.path.isfile(req_file):
        return [{'type': 'warning', 'message': "'requirements.txt' não encontrado."}]
    
    CRITICAL_PACKAGES = ['numpy', 'opencv-python', 'Pillow']
    try:
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
                            'file': req_file, 'line': line_num,
                            'snippet': _get_code_snippet(req_file, line_num, 1) # <-- SNIPPET ADICIONADO
                        })
    except IOError:
        pass # Falha silenciosa se o arquivo não puder ser lido
    return findings

def _analyze_imports(content, file_path):
    """Analisa estaticamente as declarações de import, ignorando falsos positivos comuns."""
    findings = []
    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return findings

    # Aprimoramos a lista para incluir nossa dependência opcional.
    IGNORE_LIST = {'setuptools', 'kivy'}

    for node in ast.walk(tree):
        module_name = None
        
        if isinstance(node, ast.Import):
            if node.names:
                module_name = node.names[0].name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue
            if node.module:
                module_name = node.module.split('.')[0]
        
        if module_name and module_name not in IGNORE_LIST:
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    findings.append({
                        'type': 'error',
                        'message': f"Import não resolvido: Módulo '{module_name}' não encontrado.",
                        'file': file_path, 'line': node.lineno,
                        'snippet': _get_code_snippet(file_path, node.lineno)
                    })
            except ModuleNotFoundError:
                findings.append({
                    'type': 'error',
                    'message': f"Import não resolvido: Módulo '{module_name}' não encontrado.",
                    'file': file_path, 'line': node.lineno,
                    'snippet': _get_code_snippet(file_path, node.lineno)
                })
    return findings
    
def _check_source_code(path, ignore_list=None):
    """Analisa arquivos .py com Pyflakes e outras heurísticas, com snippets."""
    findings = []
    folders_to_ignore = set(ignore_list or []) | {'venv', 'build', 'dist', '.git'}
    
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if not file.endswith('.py'): continue
            
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Análise Pyflakes
                output_stream = StringIO()
                reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
                pyflakes_api.check(content, file_path, reporter)
                
                for line_error in output_stream.getvalue().strip().splitlines():
                    parts = line_error.split(':', 2)
                    # CORREÇÃO: Verificação robusta para evitar IndexError
                    if len(parts) >= 3:
                        try:
                            line_num, message_text = int(parts[1]), parts[2].strip()
                            findings.append({
                                'type': 'error', 'message': message_text,
                                'file': file_path, 'line': line_num,
                                'snippet': _get_code_snippet(file_path, line_num)
                            })
                        except (ValueError, IndexError):
                            continue
                
                # Análise de Regex
                findings.extend(_analyze_regex_risks(content, file_path))
                findings.extend(_analyze_imports(content, file_path))
            
            except IOError:
                continue
    return findings
    
def _analyze_regex_risks(content, file_path):
    """Analisa estaticamente padrões de regex em um arquivo."""
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
                        'file': file_path, 'line': node.lineno,
                        'snippet': _get_code_snippet(file_path, node.lineno) # <-- SNIPPET ADICIONADO
                    })
    return findings