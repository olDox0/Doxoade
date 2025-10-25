# DEV.V10-20251022. >>>
# doxoade/commands/kvcheck.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 2.0(Fnc).
# Descrição: Refatora o kvcheck para usar a nova função _load_config_and_get_search_path,
# corrigindo o ImportError final da refatoração.

import os
import sys
import re

import click
from colorama import Fore

# --- CORREÇÃO: Atualiza os imports de shared_tools ---
from ..shared_tools import (
    ExecutionLogger,
    _present_results,
    _get_code_snippet,
    _load_config_and_get_search_path # Usa a nova "Fonte da Verdade"
)

__version__ = "34.0 Alfa"

@click.command('kvcheck')
@click.pass_context
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def kvcheck(ctx, ignore, format):
    """Analisa arquivos .kv em busca de problemas de design comuns."""
    arguments = ctx.params
    path = '.' # Define o path base para o logger

    with ExecutionLogger('kvcheck', path, arguments) as logger:
        if format == 'text':
            click.echo(Fore.YELLOW + f"[KV] Executando análise de .kv em '{os.path.abspath(path)}'...")
        
        # --- CORREÇÃO: Lógica de caminho robusta ---
        search_path = _load_config_and_get_search_path(logger)
        if not search_path:
            _present_results(format, logger.results)
            sys.exit(1)

        folders_to_ignore = set([item.lower().strip('/') for item in ignore] + ['venv', 'build', 'dist', '.git'])
        files_to_check = []
        for root, dirs, files in os.walk(search_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.kv'):
                    files_to_check.append(os.path.join(root, file))

        for file_path in files_to_check:
            findings = _analyze_kv_file(file_path)
            for f in findings:
                logger.add_finding(f.get('severity', 'ERROR'), f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'), snippet=f.get('snippet'))

        _present_results(format, logger.results)
        
        if logger.results['summary']['critical'] > 0 or logger.results['summary']['errors'] > 0:
            sys.exit(1)

def _analyze_kv_file(file_path):
    """Analisa um único arquivo .kv em busca de problemas conhecidos."""
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        lexer_regex = re.compile(r'^\s+lexer:\s*([\'"]\w+[\'"])')
        
        in_code_input = False
        for i, line_content in enumerate(lines):
            line_num = i + 1
            if 'CodeInput:' in line_content:
                in_code_input = True
                continue

            if in_code_input:
                match = lexer_regex.match(line_content)
                if match:
                    findings.append({
                        'severity': 'ERROR', # Usa o novo sistema de severidade
                        'message': f"A propriedade 'lexer' está definida como uma string ({match.group(1)}), o que causará um AttributeError.",
                        'details': "O lexer deve ser um objeto (ex: PythonLexer), importado no .py e passado para o .kv.",
                        'file': file_path,
                        'line': line_num,
                        'snippet': _get_code_snippet(file_path, line_num, 1)
                    })
                if not line_content.startswith((' ', '\t', '#', '\n')) and len(line_content.strip()) > 0:
                    in_code_input = False
                    
    except Exception as e:
        findings.append({'severity': 'ERROR', 'message': f"Falha ao analisar o arquivo .kv: {e}", 'file': file_path})
        
    return findings