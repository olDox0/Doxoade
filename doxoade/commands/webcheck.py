# doxoade/commands/webcheck.py
import os
import sys
import re
import ast
import logging
import esprima
import cssutils
from bs4 import BeautifulSoup

import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _present_results, _get_project_config

__version__ = "36.0 Next (Web-in-Python)"

# Silenciar logs barulhentos do cssutils
cssutils.log.setLevel(logging.CRITICAL)

@click.command('webcheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def webcheck(ctx, path, ignore, format):
    """
    Analisa ativos web (HTML/CSS/JS) e Web-in-Python (NiceGUI).
    Valida sintaxe CSS/HTML injetada via strings Python.
    """
    arguments = ctx.params
    with ExecutionLogger('webcheck', path, arguments) as logger:
        try:
            if format == 'text':
                click.echo(Fore.YELLOW + f"[WEB] Doxoade v{__version__} analisando '{os.path.abspath(path)}'...")
            
            config = _get_project_config(logger)
            final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))

            web_findings = _check_web_assets(path, final_ignore_list)
            
            for f in web_findings:
                logger.add_finding(f['type'], f['message'], category='WEB-LINT', details=f.get('details'), file=f.get('file'), line=f.get('line'))

            _present_results(format, logger.results)

            if logger.results['summary']['errors'] > 0:
                sys.exit(1)
        except Exception as e:
            logger.add_finding('CRITICAL', 'Falha inesperada no webcheck.', details=str(e))
            sys.exit(1)

def _check_web_assets(path, ignore_list=None):
    findings = []
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + 
                           ['venv', 'env', '.env', 'build', 'dist', '.git', '__pycache__', '.pytest_cache'])
    
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith(('.html', '.htm')):
                findings.extend(_analyze_html_file(full_path))
            elif file.endswith('.css'):
                findings.extend(_analyze_css_file(full_path))
            elif file.endswith('.js'):
                findings.extend(_analyze_js_file(full_path))
            elif file.endswith('.py'):
                # Nova capacidade: Web-in-Python
                findings.extend(_analyze_py_web_content(full_path))
    return findings

# --- ANALISADORES DE ARQUIVOS PUROS ---

def _analyze_html_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return _validate_html_content(f.read(), file_path)
    except Exception as e:
        return [{'type': 'error', 'message': f"Erro de leitura HTML: {e}", 'file': file_path}]

def _analyze_css_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return _validate_css_content(f.read(), file_path)
    except Exception as e:
        return [{'type': 'error', 'message': f"Erro de leitura CSS: {e}", 'file': file_path}]

def _analyze_js_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            esprima.parseScript(f.read())
        return []
    except esprima.Error as e:
        return [{'type': 'error', 'message': f"Sintaxe JS Inválida: {e.message}", 'file': file_path, 'line': e.lineNumber}]
    except Exception:
        return []

# --- NOVA CAPACIDADE: WEB-IN-PYTHON (AST) ---

def _analyze_py_web_content(file_path):
    """Extrai strings de CSS/HTML do Python e valida."""
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # 1. Busca: ui.add_head_html("...") ou element.html = "..."
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                
                # HTML em add_head_html ou html=...
                if func_name in ['add_head_html', 'html']:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        html_str = node.args[0].value
                        findings.extend(_validate_html_content(html_str, file_path, line_offset=node.lineno))

                # CSS em .style("...") ou props("...")
                if func_name in ['style', 'props']:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        css_str = node.args[0].value
                        # Para .style(), o conteúdo geralmente é "color: red; ..." (Rule Body)
                        # O cssutils espera um seletor completo. Vamos "mockar" um seletor para validar.
                        mock_css = f".mock_selector {{ {css_str} }}"
                        findings.extend(_validate_css_content(mock_css, file_path, line_offset=node.lineno, is_fragment=True))
                        
                # Validação de Segurança NiceGUI
                if func_name == 'html':
                    # Verifica se 'sanitize' foi passado
                    has_sanitize = any(k.arg == 'sanitize' for k in node.keywords)
                    if not has_sanitize:
                         findings.append({'type': 'error', 'message': "NiceGUI: ui.html() requer argumento 'sanitize=True/False'.", 'file': file_path, 'line': node.lineno})
                         
            # 2. Busca: Variáveis CSS_GLOBAL = "..."
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and ('CSS_' in target.id or 'STYLE_' in target.id):
                        if isinstance(node.value, ast.Constant):
                            css_str = node.value.value
                            findings.extend(_validate_css_content(css_str, file_path, line_offset=node.lineno))

    except Exception:
        pass # Ignora erros de parse Python (já pegos pelo check)
        
    return findings

# --- MOTORES DE VALIDAÇÃO (Reutilizáveis) ---

def _validate_html_content(content, file_path, line_offset=0):
    findings = []
    try:
        soup = BeautifulSoup(content, 'lxml')
        # Verifica tags vazias perigosas ou mal fechadas (implícito no lxml)
        for tag in soup.find_all(True):
            if tag.name == 'img' and not tag.get('alt'):
                 findings.append({'type': 'warning', 'message': "Tag <img> sem 'alt' (Acessibilidade).", 'file': file_path, 'line': line_offset})
    except Exception as e:
        findings.append({'type': 'error', 'message': f"HTML Inválido: {e}", 'file': file_path, 'line': line_offset})
    return findings

def _validate_css_content(content, file_path, line_offset=0, is_fragment=False):
    findings = []
    try:
        # Regex Rápido
        if '!important' in content and content.count('!important') > 5:
            findings.append({'type': 'warning', 'message': "Uso excessivo de '!important'.", 'file': file_path, 'line': line_offset})
            
        # CSS Utils (Parser Real)
        # Suprime stderr temporariamente pois cssutils é barulhento
        sheet = cssutils.parseString(content)
        
        for rule in sheet:
            if rule.type == rule.STYLE_RULE:
                for prop in rule.style:
                    # Validação básica de propriedades
                    if not prop.name:
                        findings.append({'type': 'error', 'message': "Propriedade CSS inválida.", 'file': file_path, 'line': line_offset})
                        
    except Exception as e:
        msg = str(e)
        if is_fragment and "No style rules found" in msg: return [] # Ignora fragmentos vazios
        findings.append({'type': 'error', 'message': f"Sintaxe CSS Inválida: {msg}", 'file': file_path, 'line': line_offset})
        
    return findings