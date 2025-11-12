# doxoade/commands/check.py
import sys
import os
import ast
import json
import subprocess
import re
import click
from colorama import Fore
from io import StringIO
from pyflakes import api as pyflakes_api
import shutil

from ..shared_tools import (
    ExecutionLogger, _present_results, _get_code_snippet,
    _get_venv_python_executable, _get_project_config, analyze_file_structure
)

# As Sondas (_STATIC_ANALYSIS_PROBE, etc.) e as funções refatoradas
# (_run_syntax_probe, _run_pyflakes_probe, etc.) permanecem as mesmas.
# Omitidas para brevidade.
_STATIC_ANALYSIS_PROBE = """
import sys
import os
import subprocess

def analyze(file_path):
    try:
        cmd = [sys.executable, '-m', 'pyflakes', file_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode
    except Exception as e:
        sys.stderr.write(f"ProbeInternalError:{file_path}:1:{type(e).__name__}: {str(e)}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(analyze(sys.argv[1]))
    else:
        sys.stderr.write("ProbeError: No file path provided.")
        sys.exit(1)
"""

_SYNTAX_ANALYSIS_PROBE = """
import sys
import ast

def analyze(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        ast.parse(content, filename=file_path)
        return 0
    except SyntaxError as e:
        line = getattr(e, 'lineno', 1)
        msg = getattr(e, 'msg', str(e))
        sys.stderr.write(f"SyntaxError:{file_path}:{line}:{msg}")
        return 1
    except Exception as e:
        sys.stderr.write(f"ProbeInternalError:{file_path}:1:{type(e).__name__}: {str(e)}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(analyze(sys.argv[1]))
    else:
        sys.stderr.write("ProbeError: No file path provided.")
        sys.exit(1)
"""

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
    """(Versão Definitiva) Coleta arquivos .py, ignorando diretórios pelo nome."""
    search_path = config.get('search_path')
    
    config_ignore = [p.strip('/\\').lower() for p in config.get('ignore', [])]
    cmd_line_ignore_list = [p.strip('/\\').lower() for p in cmd_line_ignore]
    
    folders_to_ignore = set(config_ignore + cmd_line_ignore_list)
    folders_to_ignore.update(['venv', 'build', 'dist', '.git', '__pycache__'])

    files_to_check = []
    for root, dirs, files in os.walk(search_path, topdown=True):
        # A forma correta e testada: modifica a lista 'dirs' para não visitar pastas ignoradas.
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
    return files_to_check

def _run_syntax_probe(file_path, python_executable, debug=False):
    findings = []
    syntax_cmd = [python_executable, '-c', _SYNTAX_ANALYSIS_PROBE, file_path]
    try:
        result = subprocess.run(syntax_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-SYNTAX PROBE] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda Sintaxe: {result.returncode}")
            click.echo(f"  > STDERR Sintaxe:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG-SYNTAX PROBE] ---\n")

        if result.returncode != 0:
            line_match = re.search(r':(\d+):', result.stderr)
            line_num = int(line_match.group(1)) if line_match else 1
            findings.append({'severity': 'CRITICAL', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'message': f"Falha catastrófica ao invocar a sonda de sintaxe: {e}", 'file': file_path})
    return findings

def _run_pyflakes_probe(file_path, python_executable, debug=False):
    findings = []
    pyflakes_cmd = [python_executable, '-c', _STATIC_ANALYSIS_PROBE, file_path]
    try:
        result = subprocess.run(pyflakes_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-CHECK] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda: {result.returncode}")
            click.echo(f"  > STDOUT Sonda:\n---\n{result.stdout.strip()}\n---")
            click.echo(f"  > STDERR Sonda:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG] ---\n")

        if result.stderr:
            if 'invalid syntax' in result.stderr.lower() or 'indentation' in result.stderr.lower():
                line_match = re.search(r':(\d+):', result.stderr)
                line_num = int(line_match.group(1)) if line_match else 1
                findings.append({'severity': 'CRITICAL', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
            else:
                findings.append({'severity': 'WARNING', 'message': "Sonda de análise estática reportou um erro.", 'details': result.stderr})

        for line_error in result.stdout.strip().splitlines():
            match = re.match(r'(.+?):(\d+):(\d+):\s(.+)', line_error)
            if match:
                _, line_num, _, message_text = match.groups()
                severity = 'ERROR' if 'unused' in message_text or 'redefinition' in message_text else 'WARNING'
                findings.append({'severity': severity, 'message': message_text, 'file': file_path, 'line': int(line_num)})
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'message': f"Falha catastrófica ao invocar a sonda Pyflakes: {e}", 'file': file_path})
    return findings

def _extract_imports(file_path):
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        if content.strip():
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imports.append({'module': alias.name.split('.')[0], 'line': node.lineno, 'file': file_path})
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: imports.append({'module': node.module.split('.')[0], 'line': node.lineno, 'file': file_path})
    except (SyntaxError, IOError):
        pass
    return imports

def _analyze_single_file_statically(file_path, python_executable, debug=False):
    syntax_findings = _run_syntax_probe(file_path, python_executable, debug)
    if syntax_findings:
        return syntax_findings, []
    pyflakes_findings = _run_pyflakes_probe(file_path, python_executable, debug)
    imports = _extract_imports(file_path)
    return pyflakes_findings, imports

def _run_import_probe(all_imports, venv_python, logger, search_path):
    unique_module_names = sorted(list({imp['module'] for imp in all_imports}))
    if not unique_module_names: return []
    try:
        process = subprocess.run([venv_python, "-c", _PROBE_SCRIPT], input=json.dumps(unique_module_names), capture_output=True, text=True, check=True, encoding='utf-8')
        missing_from_venv = set(json.loads(process.stdout))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.add_finding('CRITICAL', "A Sonda de Ambiente falhou.", details=str(e))
        return []
    if not missing_from_venv: return []
    truly_missing_modules = set()
    for module_name in missing_from_venv:
        potential_file = os.path.join(search_path, f"{module_name}.py")
        potential_package = os.path.join(search_path, module_name)
        if not os.path.exists(potential_file) and not os.path.isdir(potential_package):
            truly_missing_modules.add(module_name)
    if not truly_missing_modules: return []
    import_findings = []
    IGNORE_MODULES = {'setuptools', 'kivy', 'ia_core'}
    for imp in all_imports:
        if imp['module'] in truly_missing_modules and imp['module'] not in IGNORE_MODULES:
            import_findings.append({'severity': 'CRITICAL', 'message': f"Import não resolvido: Módulo '{imp['module']}' não foi encontrado.", 'file': imp['file'], 'line': imp['line'], 'snippet': _get_code_snippet(imp['file'], imp['line'])})
    return import_findings

def _fix_unused_imports(file_path, logger):
    """Comenta linhas com imports não utilizados em um arquivo."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        
        unused_import_lines = {
            int(line.split(':', 2)[1]) for line in output_stream.getvalue().strip().splitlines()
            if "' is unused" in line and 'redefinition' not in line
        }

        if not unused_import_lines: return 0

        shutil.copy(file_path, f"{file_path}.bak")
        lines = content.splitlines()
        fix_count = 0
        new_lines = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if line_num in unused_import_lines and not line.strip().startswith("#dox-fix#"):
                new_lines.append(f"#dox-fix# {line}")
                fix_count += 1
            else:
                new_lines.append(line)
        
        if fix_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(new_lines))
        
        return fix_count
    except (IOError, OSError, SyntaxError) as e:
        logger.add_finding('WARNING', f"Não foi possível processar ou corrigir o arquivo {file_path}", details=str(e))
        return 0

def run_check_logic(path, cmd_line_ignore, fix, debug):
    """Lógica pura do 'check' que retorna os resultados."""
    with ExecutionLogger('check_logic', path, {}) as logger:
        config = _get_project_config(logger, start_path=path)
        if not config.get('search_path_valid'): return logger.results

        files_to_process = _collect_files_to_analyze(config, cmd_line_ignore)
        
        if fix:
            click.echo(Fore.CYAN + "Modo de correção (--fix) ativado...")
            total_fixed = 0
            for file_path in files_to_process:
                total_fixed += _fix_unused_imports(file_path, logger)

        all_imports = []
        logger.results['file_reports'] = {}
        python_executable = _get_venv_python_executable()

        if not python_executable:
            logger.add_finding('CRITICAL', "Ambiente virtual 'venv' não encontrado ou inválido.")
        else:
            for file in files_to_process:
                static_findings, imports = _analyze_single_file_statically(file, python_executable, debug)
                structure_analysis = analyze_file_structure(file)
                rel_file_path = os.path.relpath(file, path) if path != '.' else file
                logger.results['file_reports'][rel_file_path] = {
                    'static_analysis': {'findings': static_findings, 'imports': imports},
                    'structure_analysis': structure_analysis
                }
                for finding in static_findings:
                    snippet = _get_code_snippet(finding.get('file'), finding.get('line'))
                    logger.add_finding(finding['severity'], finding['message'], file=finding['file'], line=finding['line'], snippet=snippet)
                all_imports.extend(imports)

            if all_imports:
                import_findings = _run_import_probe(all_imports, python_executable, logger, config.get('search_path'))
                for f in import_findings:
                    logger.add_finding(f['severity'], f['message'], file=f['file'], line=f['line'], snippet=f.get('snippet'))

        for report in logger.results['file_reports'].values():
            report['static_analysis']['findings'] = []
            
        # Repopula com os findings completos do logger (que contêm o 'hash')
        for finding in logger.results['findings']:
            file_path = finding.get('file')
            if file_path in logger.results['file_reports']:
                logger.results['file_reports'][file_path]['static_analysis']['findings'].append(finding)

        return logger.results

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', 'cmd_line_ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas automaticamente.")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração detalhada.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def check(ctx, path, cmd_line_ignore, fix, debug, output_format):
    """Análise estática e estrutural completa do projeto."""
    if not debug and output_format == 'text':
        click.echo(Fore.YELLOW + "[CHECK] Executando análise...")
        
    results = run_check_logic(path, cmd_line_ignore, fix, debug)
    
    if output_format == 'json':
        if 'findings' in results: del results['findings']
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not debug:
            _present_results('text', results)
    
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)