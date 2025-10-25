# DEV.V10-20251022. >>>
# doxoade/commands/check.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 9.0(Fnc).
# Descrição: CORREÇÃO DE CONFIGURAÇÃO FINAL. Garante que a lista 'ignore' do pyproject.toml
# seja corretamente combinada com a da linha de comando e usada pela análise.

import sys, os, ast, json, subprocess
from io import StringIO
from pyflakes import api as pyflakes_api
import click
from colorama import Fore

from ..shared_tools import (
    ExecutionLogger, 
    _present_results, 
    _get_code_snippet,
    _get_venv_python_executable, 
    _get_project_config
)

# --- SONDA DE AMBIENTE ---
# A sonda é agora uma string auto-contida, garantindo portabilidade.
_PROBE_SCRIPT = """
import sys, json, importlib.util
def check_modules(modules_to_check):
    missing = []
    for module_name in modules_to_check:
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ValueError, ImportError):
            pass
    return missing
if __name__ == "__main__":
    input_data = sys.stdin.read()
    modules = json.loads(input_data)
    missing_modules = check_modules(modules)
    print(json.dumps(missing_modules))
"""

# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 6.1(Fnc).
# Descrição: CORREÇÃO DE CONFIGURAÇÃO FINAL. A lógica de 'ignore' agora normaliza os caminhos,
# removendo barras, para garantir que a diretiva do pyproject.toml seja respeitada.
def _check_source_code(ignore_list, logger):
    """Orquestra a análise de código-fonte."""
    config = _get_project_config(logger)
    if not config.get('search_path_valid'):
        return
    search_path = config.get('search_path')

    files_to_check = []
    all_imports = {}
    
    # Normaliza a lista de ignorados, removendo barras e convertendo para minúsculas.
    normalized_ignore_list = {item.lower().strip('/\\') for item in ignore_list}
    
    folders_to_ignore = normalized_ignore_list | {'venv', 'build', 'dist', '.git'}
    
    for root, dirs, files in os.walk(search_path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
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
                except (SyntaxError, IOError) as e:
                    line_num = getattr(e, 'lineno', None)
                    logger.add_finding(
                        'CRITICAL', 
                        "Erro de sintaxe impede a análise.", 
                        file=file_path, 
                        line=line_num,
                        snippet=_get_code_snippet(file_path, line_num)
                    )
                    continue

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
            logger.add_finding('CRITICAL', "A Sonda de Ambiente falhou. A verificação de dependências não é confiável.", details=str(e))
            
    for file_path in files_to_check:
        if file_path in all_imports:
            for module_name, line_num in all_imports[file_path]:
                if module_name in missing_modules and module_name not in ['ia_core', 'setuptools', 'kivy']:
                    logger.add_finding('CRITICAL', f"Import não resolvido: Módulo '{module_name}' não foi encontrado no venv.",
                                    file=file_path, line=line_num, snippet=_get_code_snippet(file_path, line_num))
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            output_stream = StringIO()
            reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
            pyflakes_api.check(content, file_path, reporter)
            for line_error in output_stream.getvalue().strip().splitlines():
                parts = line_error.split(':', 2)
                if len(parts) >= 3:
                    try:
                        line_num, message_text = int(parts[1]), parts[2].strip()
                        logger.add_finding('ERROR', message_text,
                                        file=file_path, line=line_num,
                                        snippet=_get_code_snippet(file_path, line_num))
                    except (ValueError, IndexError):
                        continue
        except IOError:
            continue

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', 'cmd_line_ignore', multiple=True, help="Ignora uma pasta.")
def check(ctx, path, cmd_line_ignore):
    """Análise estática completa do projeto com verificação de ambiente via sonda."""
    arguments = ctx.params
    with ExecutionLogger('check', path, arguments) as logger:
        click.echo(Fore.YELLOW + "[CHECK] Executando análise de integridade do projeto...")
        
        # --- LÓGICA DE IGNORE CORRIGIDA ---
        config = _get_project_config(logger)
        config_ignore = config.get('ignore', [])
        
        # Combina as duas listas, garantindo que ambas sejam tratadas como listas
        final_ignore_list = list(set(config_ignore + list(cmd_line_ignore)))
        # --- FIM DA CORREÇÃO ---

        _check_source_code(final_ignore_list, logger)

        _present_results('text', logger.results)
        
        if logger.results['summary']['critical'] > 0:
            sys.exit(1)