# doxoade/doxoade/commands/webcheck.py
"""
Módulo de Auditoria Web e Web-in-Python (NiceGUI).
Realiza análise estática em arquivos HTML, CSS, JS e extrai strings de 
tecnologias web embutidas em código Python via AST.
Otimizado para Termux: utiliza 'html.parser' nativo em vez de 'lxml'.
"""
import os
import sys
import ast
import logging
import esprima
import cssutils
from bs4 import BeautifulSoup
import click
from doxoade.tools.doxcolors import Fore
from doxoade.probes.web_probe import WebAuditProbe
from doxoade.tools.display import _present_results
from doxoade.commands.doxcolors_systems.colors_command import config
from doxoade.tools.filesystem import _get_project_config
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
try:
    import requests
except ImportError:
    requests = None
__version__ = '36.1 Alfa (Termux-Safe)'
cssutils.log.setLevel(logging.CRITICAL)

@click.command('webcheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=True), default='.')
@click.option('--ignore', multiple=True, help='Ignores specific folders.')
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format.')
def webcheck(ctx, path, ignore, format):
    """Realiza Auditoria Web Sênior (Peso, Assets e Visual)."""
    if path is None:
        raise ValueError('O caminho de análise não pode ser nulo.')
    arguments = ctx.params
    with ExecutionLogger('webcheck', path, arguments) as logger:
        try:
            probe = WebAuditProbe(path)
            for f in probe.audit_payloads():
                logger.add_finding('CRITICAL', f['msg'], file=f.get('file'))
            for f in probe.audit_visuals():
                logger.add_finding('WARNING', f['msg'], file=f.get('file'))
            for f in probe.check_cdn_health():
                logger.add_finding('ERROR', f['msg'])
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
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = sys.exc_info()
            print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
            exc_trace(exc_tb)
            logger.add_finding('CRITICAL', 'Falha inesperada no webcheck.', details=str(e))
            sys.exit(1)

def _check_web_assets(path: str, ignore_list: list=None):
    """
    Varre o sistema de arquivos em busca de ativos web e arquivos Python.
    """
    findings = []
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'env', '.env', 'build', 'dist', '.git', '__pycache__', '.pytest_cache'])
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
                findings.extend(_analyze_py_web_content(full_path))
    return findings

def _analyze_html_file(file_path: str):
    """Lê e valida o conteúdo de um arquivo HTML físico."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return _validate_html_content(f.read(), file_path)
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        return [{'type': 'error', 'message': f'Erro de leitura HTML: {e}', 'file': file_path}]

def _analyze_css_file(file_path: str):
    """Lê e valida o conteúdo de um arquivo CSS físico."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return _validate_css_content(f.read(), file_path)
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        return [{'type': 'error', 'message': f'Erro de leitura CSS: {e}', 'file': file_path}]

def _analyze_js_file(file_path: str):
    """Realiza o parse de arquivos JavaScript para validar a sintaxe básica."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            esprima.parseScript(f.read())
        return []
    except esprima.Error as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        return [{'type': 'error', 'message': f'Sintaxe JS Inválida: {e.message}', 'file': file_path, 'line': e.lineNumber}]
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        return [{'type': 'warning', 'message': f'Falha no parser JS: {str(e)}', 'file': file_path}]

def _analyze_py_web_content(file_path: str):
    """
    Extrai strings de CSS/HTML de chamadas NiceGUI/Python e as valida individualmente.
    """
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ''
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                if func_name in ['add_head_html', 'html']:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        html_str = node.args[0].value
                        findings.extend(_validate_html_content(html_str, file_path, line_offset=node.lineno))
                if func_name in ['style', 'props']:
                    if node.args and isinstance(node.args[0], ast.Constant):
                        css_str = node.args[0].value
                        mock_css = f'.mock_selector {{ {css_str} }}'
                        findings.extend(_validate_css_content(mock_css, file_path, line_offset=node.lineno, is_fragment=True))
                if func_name == 'html':
                    has_sanitize = any((k.arg == 'sanitize' for k in node.keywords))
                    if not has_sanitize:
                        findings.append({'type': 'error', 'message': "Segurança: ui.html() requer argumento 'sanitize' explícito.", 'file': file_path, 'line': node.lineno})
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and ('CSS_' in target.id or 'STYLE_' in target.id):
                        if isinstance(node.value, ast.Constant):
                            css_str = node.value.value
                            findings.extend(_validate_css_content(css_str, file_path, line_offset=node.lineno))
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        logging.debug(f'Falha ao analisar AST web em {file_path}: {e}')
    return findings

def _validate_html_content(content: str, file_path: str, line_offset: int=0):
    """
    Valida HTML utilizando o parser nativo para evitar dependência de binários lxml.
    """
    findings = []
    try:
        soup = BeautifulSoup(content, 'html.parser')
        for tag in soup.find_all(True):
            if tag.name == 'img' and (not tag.get('alt')):
                findings.append({'type': 'warning', 'message': "Acessibilidade: Tag <img> sem atributo 'alt'.", 'file': file_path, 'line': line_offset})
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        findings.append({'type': 'error', 'message': f'HTML Inválido: {e}', 'file': file_path, 'line': line_offset})
    return findings

def _validate_css_content(content: str, file_path: str, line_offset: int=0, is_fragment: bool=False):
    """
    Valida a sintaxe CSS capturando erros do log interno do cssutils.
    """
    if content is None:
        raise ValueError('O conteúdo CSS para validação não pode ser nulo.')
    if not file_path:
        raise ValueError('O caminho do arquivo é obrigatório para o rastreio de erros.')
    findings = []
    css_errors = []

    class CSSCaptureHandler(logging.Handler):

        def emit(self, record):
            css_errors.append(record.getMessage())
    capture_handler = CSSCaptureHandler()
    cssutils.log.addHandler(capture_handler)
    cssutils.log.setLevel(logging.ERROR)
    try:
        if '!important' in content and content.count('!important') > 5:
            findings.append({'type': 'warning', 'message': "CSS: Uso excessivo de '!important'.", 'file': file_path, 'line': line_offset})
        sheet = cssutils.parseString(content)
        for error_msg in css_errors:
            findings.append({'type': 'error', 'message': f'Sintaxe CSS: {error_msg}', 'file': file_path, 'line': line_offset})
        if is_fragment and len(sheet.cssRules) == 0 and (not css_errors):
            findings.append({'type': 'error', 'message': 'Sintaxe CSS: O fragmento de estilo não produziu regras válidas.', 'file': file_path, 'line': line_offset})
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\n')
        exc_trace(exc_tb)
        findings.append({'type': 'error', 'message': f'Sintaxe CSS Fatal: {str(e)}', 'file': file_path, 'line': line_offset})
    finally:
        cssutils.log.removeHandler(capture_handler)
    return findings
