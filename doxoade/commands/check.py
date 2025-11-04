# DEV.V10-20251022. >>>
# doxoade/commands/check.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 12.1(Fnc).
# Descrição: CORREÇÃO DE REGRESSÃO. Restaura a importação de 'ExecutionLogger'
# que foi acidentalmente removida, resolvendo o NameError.

import sys, os, ast, json, subprocess
from io import StringIO
from pyflakes import api as pyflakes_api
import click
from colorama import Fore


from ..shared_tools import (
    ExecutionLogger, # <-- RESTAURE ESTA LINHA
    _present_results, 
    _get_code_snippet,
    _get_venv_python_executable, 
    _get_project_config
)

_PROBE_SCRIPT = """
import sys, json, importlib.util
def check_modules(modules_to_check):
    missing = []
    for module_name in modules_to_check:
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ValueError, ImportError): pass
    return missing
if __name__ == "__main__":
    print(json.dumps(check_modules(json.loads(sys.stdin.read()))))
"""

def _collect_files_to_analyze(config, cmd_line_ignore):
    """Encontra todos os arquivos .py que devem ser analisados."""
    search_path = config.get('search_path')
    
    config_ignore = [item.strip('/\\') for item in config.get('ignore', [])]
    folders_to_ignore = set([item.lower() for item in config_ignore + list(cmd_line_ignore)] + ['venv', 'build', 'dist', '.git'])
    
    files_to_check = []
    # A busca agora começa a partir do search_path
    for root, dirs, files in os.walk(search_path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
                
    return files_to_check

def _analyze_single_file_statically(file_path):
    """Executa Pyflakes e extrai imports de um único arquivo."""
    findings = []
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if not content.strip():
            return [], []

        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        for line_error in output_stream.getvalue().strip().splitlines():
            parts = line_error.split(':', 2)
            if len(parts) >= 3:
                try:
                    line_num, message_text = int(parts[1]), parts[2].strip()
                    findings.append({
                        'severity': 'ERROR', 'message': message_text, 
                        'file': file_path, 'line': line_num,
                        'snippet': _get_code_snippet(file_path, line_num)
                    })
                except (ValueError, IndexError):
                    continue

        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({'module': alias.name.split('.')[0], 'line': node.lineno, 'file': file_path})
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.append({'module': node.module.split('.')[0], 'line': node.lineno, 'file': file_path})
                
    except (SyntaxError, IOError) as e:
        line_num = getattr(e, 'lineno', None)
        findings.append({
            'severity': 'CRITICAL', 'message': "Erro de sintaxe impede a análise.",
            'file': file_path, 'line': line_num,
            'snippet': _get_code_snippet(file_path, line_num)
        })

    return findings, imports

def _run_import_probe(all_imports, venv_python, logger, search_path):
    """Executa a Sonda de Ambiente e valida imports contra pacotes locais."""
    unique_module_names = sorted(list({imp['module'] for imp in all_imports}))
    if not unique_module_names:
        return []

    # --- UTILITARIO 1: Executar Sonda de Ambiente para Pacotes Instalados ---
    try:
        process = subprocess.run(
            [venv_python, "-c", _PROBE_SCRIPT],
            input=json.dumps(unique_module_names),
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        missing_from_venv = set(json.loads(process.stdout))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.add_finding('CRITICAL', "A Sonda de Ambiente falhou.", details=str(e))
        return []

    if not missing_from_venv:
        return [] # Todos os imports foram resolvidos no venv, trabalho concluído.

    # --- UTILITARIO 2: Verificação de Pacotes Locais (A Correção Chave) ---
    truly_missing_modules = set()
    for module_name in missing_from_venv:
        # FLUXO 1: Verificar se o módulo corresponde a um arquivo .py
        potential_file = os.path.join(search_path, f"{module_name}.py")
        
        # FLUXO 2: Verificar se o módulo corresponde a uma pasta (pacote)
        potential_package = os.path.join(search_path, module_name)
        
        if not os.path.exists(potential_file) and not os.path.isdir(potential_package):
            truly_missing_modules.add(module_name)
    
    if not truly_missing_modules:
        return [] # Todos os "ausentes" foram encontrados como pacotes locais.

    # --- UTILITARIO 3: Gerar Findings Apenas para Módulos Realmente Ausentes ---
    import_findings = []
    # --- A Correção Chave: Lista de Exceções ---
    IGNORE_MODULES = {'setuptools', 'kivy', 'ia_core'} # Módulos a ignorar
    
    for imp in all_imports:
        if imp['module'] in truly_missing_modules and imp['module'] not in IGNORE_MODULES:
            import_findings.append({
                'severity': 'CRITICAL',
                'message': f"Import não resolvido: Módulo '{imp['module']}' não foi encontrado no venv nem como um pacote local.",
                'file': imp['file'], 'line': imp['line'],
                'snippet': _get_code_snippet(imp['file'], imp['line'])
            })
    return import_findings

def _orchestrate_check_analysis(cmd_line_ignore, logger, start_path='.'):
    """Orquestra todo o processo de análise do 'check'."""
    config = _get_project_config(logger, start_path=start_path)
    click.echo(f"DEBUG [check]: root_path = {config.get('root_path')}")
    click.echo(f"DEBUG [check]: search_path = {config.get('search_path')}")

    if not config.get('search_path_valid'):
        return

    files_to_check = _collect_files_to_analyze(config, cmd_line_ignore)

    click.echo(f"DEBUG [check]: files_to_check = {files_to_check}")
    
    all_static_findings = []
    all_imports = []

    click.echo(Fore.CYAN + f"[DEBUG] Analisando {len(files_to_check)} arquivos sequencialmente...")
    for file_path in files_to_check:
        findings, imports = _analyze_single_file_statically(file_path)
        all_static_findings.extend(findings)
        all_imports.extend(imports)

    venv_python = _get_venv_python_executable()
    if not venv_python:
        logger.add_finding('CRITICAL', "Ambiente virtual 'venv' não encontrado.")
    else:
        import_findings = _run_import_probe(all_imports, venv_python, logger, config.get('search_path'))
        all_static_findings.extend(import_findings)

    for f in all_static_findings:
        logger.add_finding(f.get('severity'), f.get('message'), file=f.get('file'), 
                           line=f.get('line'), snippet=f.get('snippet'))

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', 'cmd_line_ignore', multiple=True, help="Ignora uma pasta.")
def check(ctx, path, cmd_line_ignore):
    """Análise estática completa do projeto com verificação de ambiente via sonda."""
    arguments = ctx.params
    with ExecutionLogger('check', path, arguments) as logger:
        click.echo(Fore.YELLOW + "[CHECK] Executando análise de integridade do projeto...")
        
        _orchestrate_check_analysis(cmd_line_ignore, logger, path)

        _present_results('text', logger.results)
        
        if logger.results['summary']['critical'] > 0:
            sys.exit(1)