# DEV.V10-20251021. >>>
# doxoade/commands/check.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 2.0(Fnc).
# Descrição: Refatoração arquitetural completa. Implementa a Sonda de Ambiente para verificação precisa de imports
# e introduz Níveis de Severidade para uma análise mais inteligente e flexível.

import sys
import os
import ast
import json
import subprocess
from io import StringIO
from pyflakes import api as pyflakes_api

import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _present_results, _get_code_snippet, _load_config, _get_venv_python_executable

# --- SONDA DE AMBIENTE ---
# A sonda é agora uma string auto-contida, garantindo portabilidade.
_PROBE_SCRIPT = """
import sys, json, importlib.util

def check_modules(modules_to_check):
    missing = []
    for module_name in modules_to_check:
        try:
            # Usamos find_spec, que é a maneira mais robusta de verificar a existência de um módulo.
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ValueError, ImportError):
            # Ignora erros de 'find_spec' para nomes de módulo inválidos.
            pass
    return missing

if __name__ == "__main__":
    # Lê a lista de módulos do stdin para evitar problemas com argumentos de linha de comando.
    input_data = sys.stdin.read()
    modules = json.loads(input_data)
    missing_modules = check_modules(modules)
    # Retorna o resultado como JSON para stdout.
    print(json.dumps(missing_modules))
"""

# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 2.2(Fnc).
# Descrição: Corrige AttributeError ao usar a API correta do Pyflakes (modReporter.Reporter).
def _check_source_code(path, ignore_list, logger):
    """Analisa arquivos .py, orquestrando pyflakes e a verificação de imports com a sonda."""
    
    # --- Utilitário 1: Coletar todos os arquivos e todos os imports ---
    files_to_check = []
    all_imports = {} # Mapeia nome do arquivo para uma lista de (nome_modulo, linha)
    folders_to_ignore = set(ignore_list) | {'venv', 'build', 'dist', '.git'}
    
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if not file.endswith('.py'): continue
            file_path = os.path.join(root, file)
            files_to_check.append(file_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                tree = ast.parse(content, filename=file_path)
                file_imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            file_imports.append((alias.name.split('.')[0], node.lineno))
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        file_imports.append((node.module.split('.')[0], node.lineno))
                all_imports[file_path] = file_imports
            except (SyntaxError, IOError):
                logger.add_finding('ERROR', "Erro de sintaxe impede a análise.", file=file_path)
                continue # Pula para o próximo arquivo se este estiver quebrado

    # --- Utilitário 2: Executar a Sonda de Ambiente (uma única vez para todos os imports) ---
    unique_module_names = sorted(list({imp[0] for imports in all_imports.values() for imp in imports}))
    missing_modules = set()
    venv_python = _get_venv_python_executable()

    if not venv_python:
        logger.add_finding('CRITICAL', "Ambiente virtual 'venv' não encontrado.", details="A verificação de dependências não pode ser concluída.")
    elif unique_module_names:
        try:
            process = subprocess.run(
                [venv_python, "-c", _PROBE_SCRIPT],
                input=json.dumps(unique_module_names),
                capture_output=True, text=True, check=True, encoding='utf-8'
            )
            missing_modules = set(json.loads(process.stdout))
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.add_finding('ERROR', "Falha ao executar a sonda de ambiente para verificar imports.", details=str(e))

    # --- Utilitário 3: Analisar cada arquivo e agregar os resultados ---
    for file_path in files_to_check:
        # --- Fluxo 1: Reportar imports ausentes (com base no resultado da sonda) ---
        if file_path in all_imports:
            for module_name, line_num in all_imports[file_path]:
                # Ignora o 'ia_core' pois é um módulo local do projeto, não uma dependência de venv
                if module_name in missing_modules and module_name != 'ia_core':
                    logger.add_finding('CRITICAL', f"Import não resolvido: Módulo '{module_name}' não foi encontrado no venv.",
                                    file=file_path, line=line_num, snippet=_get_code_snippet(file_path, line_num))
        
        # --- Fluxo 2: Análise Pyflakes e de Regex ---
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Análise Pyflakes
            output_stream = StringIO()
            reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
            pyflakes_api.check(content, file_path, reporter)
            
            for line_error in output_stream.getvalue().strip().splitlines():
                parts = line_error.split(':', 2)
                if len(parts) >= 3:
                    try:
                        line_num, message_text = int(parts[1]), parts[2].strip()
                        # Classificamos como ERROR, não CRITICAL
                        logger.add_finding('ERROR', message_text,
                                        file=file_path, line=line_num,
                                        snippet=_get_code_snippet(file_path, line_num))
                    except (ValueError, IndexError):
                        continue
            
            # Análise de Regex (se a função existir)
            # (Vamos assumir que _analyze_regex_risks também está em check.py)
            # for finding in _analyze_regex_risks(content, file_path):
            #     logger.add_finding(**finding) # Descompacta o dicionário
                
        except IOError:
            continue # Já foi logado anteriormente
    
@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
def check(ctx, path, ignore):
    """Análise estática completa do projeto com verificação de ambiente via sonda."""
    arguments = ctx.params
    with ExecutionLogger('check', path, arguments) as logger:
        click.echo(Fore.YELLOW + "[CHECK] Executando análise de integridade do projeto...")
        
        config = _load_config()
        final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))

        _check_source_code(path, final_ignore_list, logger)

        _present_results('text', logger.results) # Formato fixo por enquanto
        
        # --- NOVA LÓGICA DE SAÍDA ---
        if logger.results['summary']['critical'] > 0:
            sys.exit(1) # Só falha o pipeline se houver erros CRÍTICOS