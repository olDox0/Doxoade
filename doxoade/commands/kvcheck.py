# doxoade/commands/kvcheck.py
import os
import sys
import re

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _load_config,
    _present_results,
    _get_code_snippet
)

__version__ = "34.0 Alfa"

@click.command('kvcheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=True), required=False, default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def kvcheck(ctx, path, ignore, format):
    """Analisa arquivos .kv em busca de problemas de design comuns."""
    arguments = ctx.params

    with ExecutionLogger('kvcheck', path, arguments) as logger:
        if format == 'text':
            click.echo(Fore.YELLOW + f"[KV] Executando análise de .kv em '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))
        
        folders_to_ignore = set([item.lower().strip('/') for item in final_ignore_list] + ['venv', 'build', 'dist', '.git'])
        files_to_check = []
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path, topdown=True):
                dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
                for file in files:
                    if file.endswith('.kv'):
                        files_to_check.append(os.path.join(root, file))
        elif path.endswith('.kv'):
            files_to_check.append(path)

        for file_path in files_to_check:
            findings = _analyze_kv_file(file_path)
            for f in findings:
                logger.add_finding(f['type'], f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'), snippet=f.get('snippet'))

        _present_results(format, logger.results)
        
        if logger.results['summary']['errors'] > 0:
            sys.exit(1)

def _analyze_kv_file(file_path):
    """Analisa um único arquivo .kv em busca de problemas conhecidos."""
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Padrão para encontrar um CodeInput onde o lexer é uma string literal
        lexer_regex = re.compile(r'^\s+lexer:\s*([\'"]\w+[\'"])')
        
        in_code_input = False
        for i, line_content in enumerate(lines):
            line_num = i + 1
            # Se encontrarmos um widget CodeInput, ativamos a flag
            if 'CodeInput:' in line_content:
                in_code_input = True
                continue

            if in_code_input:
                match = lexer_regex.match(line_content)
                if match:
                    findings.append({
                        'type': 'error',
                        'message': f"A propriedade 'lexer' está definida como uma string ({match.group(1)}), o que causará um AttributeError.",
                        'details': "O lexer deve ser um objeto (ex: PythonLexer), importado no .py e passado para o .kv.",
                        'file': file_path,
                        'line': line_num,
                        'snippet': _get_code_snippet(file_path, line_num, 1)
                    })
                # Se a indentação voltar ou encontrarmos outro widget, saímos do bloco
                if not line_content.startswith((' ', '\t', '#', '\n')) and len(line_content.strip()) > 0:
                    in_code_input = False
                    
    except Exception as e:
        findings.append({'type': 'error', 'message': f"Falha ao analisar o arquivo .kv: {e}", 'file': file_path})
        
    return findings