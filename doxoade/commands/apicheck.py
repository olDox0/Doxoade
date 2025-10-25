# doxoade/commands/apicheck.py
import ast
import os
import sys
import json

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _present_results,
    _load_config_and_get_search_path
)

__version__ = "34.0 Alfa"

@click.command('apicheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def apicheck(ctx, path, ignore, format):
    """Analisa o uso de APIs com base em um arquivo de contrato 'apicheck.json'."""
    arguments = ctx.params
    with ExecutionLogger('apicheck', path, arguments) as logger:
        if format == 'text':
            click.echo(Fore.YELLOW + f"[APICHECK] Executando análise de contratos de API em '{path}'...")
    
        search_path = _load_config_and_get_search_path(logger)
        if not search_path:
            _present_results(format, logger.results)
            sys.exit(1)
            
        # --- Passo 1: Carregar o Contrato ---
        contract_file = os.path.join(path, 'apicheck.json')
        if not os.path.exists(contract_file):
            logger.add_finding('warning', "Arquivo 'apicheck.json' não encontrado. Nenhuma análise será feita.")
            click.echo(Fore.YELLOW + "[AVISO] Arquivo 'apicheck.json' não encontrado.")
            _present_results(format, logger.results)
            return
    
        try:
            with open(contract_file, 'r', encoding='utf-8') as f:
                contracts = json.load(f).get('contracts', [])
        except (json.JSONDecodeError, IOError) as e:
            logger.add_finding('error', f"Falha ao ler ou decodificar 'apicheck.json': {e}")
            click.echo(Fore.RED + f"[ERRO] Falha ao ler ou decodificar 'apicheck.json': {e}")
            sys.exit(1)
    
        # --- Passo 2: Encontrar Arquivos e Analisar ---
        config = _load_config()
        final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))
        folders_to_ignore = set([item.lower() for item in final_ignore_list] + ['venv', 'build', 'dist', '.git'])
        files_to_check = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    files_to_check.append(os.path.join(root, file))
    
        for file_path in files_to_check:
            api_findings = _analyze_api_calls(file_path, contracts)
            for f in api_findings:
                logger.add_finding(f['type'], f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'))

        _present_results(format, logger.results)
    
        if logger.results['summary']['errors'] > 0:
            sys.exit(1)

def _analyze_api_calls(file_path, contracts):
    """Orquestra a análise de chamadas de API."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (SyntaxError, IOError):
        return []

    all_findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            full_func_name = _get_full_function_name(node)
            for contract in contracts:
                if contract.get('function') == full_func_name:
                    all_findings.extend(_validate_call_against_contract(node, contract, file_path))
    return all_findings

def _get_full_function_name(call_node):
    """Reconstrói o nome completo de uma chamada de função a partir de um nó AST."""
    func = call_node.func
    parts = []
    while isinstance(func, ast.Attribute):
        parts.insert(0, func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.insert(0, func.id)
    return ".".join(parts)

def _validate_call_against_contract(node, contract, file_path):
    """Valida um único nó de chamada contra as regras de um único contrato."""
    findings = []
    rules = contract.get('rules', {})
    provided_args = {kw.arg for kw in node.keywords}

    # Valida parâmetros obrigatórios
    for param in rules.get('required_params', []):
        if param not in provided_args:
            findings.append({
                'type': 'error', 'message': f"Chamada para '{contract.get('function')}' não possui o parâmetro obrigatório '{param}'.",
                'details': f"Contrato '{contract.get('id')}' exige este parâmetro.",
                'file': file_path, 'line': node.lineno
            })

    # Valida parâmetros proibidos
    for param, bad_value in rules.get('forbidden_params', {}).items():
        for kw in node.keywords:
            if kw.arg == param and isinstance(kw.value, ast.Constant) and kw.value.value == bad_value:
                findings.append({
                    'type': 'error', 'message': f"Chamada para '{contract.get('function')}' usa o valor proibido '{param}={bad_value}'.",
                    'details': f"Contrato '{contract.get('id')}' proíbe este uso.",
                    'file': file_path, 'line': node.lineno
                })
    return findings