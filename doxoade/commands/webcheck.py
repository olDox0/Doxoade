# doxoade/commands/webcheck.py
import os
import sys
import re
import esprima
from bs4 import BeautifulSoup

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _load_config,
    _present_results,
    #_update_summary_from_findings
)

__version__ = "34.0 Alfa"

@click.command('webcheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def webcheck(ctx, path, ignore, format):
    """Analisa arquivos .html, .css e .js em busca de problemas comuns."""
    arguments = ctx.params
    with ExecutionLogger('webcheck', path, arguments) as logger:
        try:
            if format == 'text':
                click.echo(Fore.YELLOW + f"[WEB] Executando 'doxoade webcheck' no diretório '{os.path.abspath(path)}'...")
            config = _load_config()
            final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))

            web_findings = _check_web_assets(path, final_ignore_list)
            for f in web_findings:
                logger.add_finding(f['type'], f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'))

            _present_results(format, logger.results)

            if logger.results['summary']['errors'] > 0:
                sys.exit(1)
        except Exception as e:
            safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
            click.echo(Fore.RED + f"\n[ERRO FATAL] O 'webcheck' falhou inesperadamente: {safe_error}", err=True)
            logger.add_finding('fatal_error', 'O webcheck falhou inesperadamente.', details=str(e))
            sys.exit(1)

def _check_web_assets(path, ignore_list=None):
    """Analisa arquivos web e retorna uma lista de problemas."""
    findings = []
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith(('.html', '.htm', '.css', '.js')):
                files_to_check.append(os.path.join(root, file))
    
    for file_path in files_to_check:
        if file_path.endswith(('.html', '.htm')):
            findings.extend(_analyze_html_file(file_path))
        elif file_path.endswith('.css'):
            findings.extend(_analyze_css_file(file_path))
        elif file_path.endswith('.js'):
            findings.extend(_analyze_js_file(file_path))
    return findings

def _analyze_html_file(file_path):
    findings = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'lxml')
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        if any(p in href for p in ['{{', '{%']) or href.startswith(('http', '#', 'mailto:', 'javascript:')):
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(file_path), href))
        if not os.path.exists(target):
            findings.append({'type': 'error', 'message': f"Link quebrado para '{href}'", 'file': file_path})
    for tag in soup.find_all('img', alt=None):
        findings.append({'type': 'warning', 'message': f"Imagem sem atributo 'alt' (src: {tag.get('src', 'N/A')[:50]}...)", 'file': file_path})
    return findings

def _analyze_css_file(file_path):
    findings = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if content.lower().count('!important') > 3:
        findings.append({'type': 'warning', 'message': "Uso excessivo de '!important'", 'details': "Pode indicar problemas de especificidade.", 'file': file_path})
    if re.search(r'^\s*#\w|[\{,]\s*#\w', content):
        findings.append({'type': 'warning', 'message': "Seletor de ID ('#') encontrado.", 'details': "Pode criar regras muito específicas e difíceis de manter.", 'file': file_path})
    for match in re.finditer(r'url\(([^)]+)\)', content):
        url_path = match.group(1).strip(' \'"')
        if url_path.startswith(('data:', 'http', '//', '#')):
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(file_path), url_path))
        if not os.path.exists(target):
            findings.append({'type': 'error', 'message': f"Link 'url()' quebrado para '{url_path}'", 'file': file_path})
    return findings

def _analyze_js_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    try:
        esprima.parseScript(content)
        return []
    except esprima.Error as e:
        return [{'type': 'error', 'message': f"Erro de sintaxe JS: {e.message}", 'file': file_path, 'line': e.lineNumber}]