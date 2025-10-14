# doxoade/commands/health.py
import os
import sys
import json
import subprocess
import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado (nível acima)
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _present_results, 
    _load_config,
)
# NENHUMA importação de 'doxoade.doxoade' deve estar aqui.

__version__ = "33.0 Alfa"

@click.command('health')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--complexity-threshold', default=10, help="Nível de complexidade.", type=int)
@click.option('--min-coverage', default=70, help="Cobertura de testes mínima.", type=int)
def health(ctx, path, ignore, format, complexity_threshold, min_coverage):
    #2025/10/11 - 33.0(Ver), 2.0(Fnc). Refatorada para reduzir complexidade.
    #A função agora orquestra as etapas da análise de saúde.
    arguments = ctx.params
    with ExecutionLogger('health', path, arguments) as logger:
        if not _handle_missing_venv(ctx, path, logger):
            return

        if format == 'text': click.echo(Fore.YELLOW + "[HEALTH] Executando 'doxoade health'...")
        
        findings = _run_all_analyses(path, list(ignore), complexity_threshold, min_coverage)
        for f in findings:
            logger.add_finding(f['type'], f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'))

        if not _handle_dependency_errors(ctx, path, logger):
            return

        _present_results(format, logger.results)

        if logger.results['summary'].get('errors', 0) > 0:
            sys.exit(1)

def _handle_missing_venv(ctx, path, logger):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo verificar o venv e solicitar a configuração se ausente.
    if not _get_venv_python_executable():
        logger.add_finding('warning', "Projeto sem ambiente virtual ('venv') configurado.")
        click.echo(Fore.YELLOW + "[AVISO] Este projeto não possui um ambiente virtual ('venv') configurado.")
        if click.confirm(Fore.CYAN + "Deseja executar 'doxoade setup-health' para configurá-lo?"):
            setup_health_command = ctx.parent.get_command(ctx, 'setup-health')
            ctx.invoke(setup_health_command, path=path)
            click.echo(Fore.CYAN + Style.BRIGHT + "\nConfiguração concluída. Por favor, execute 'doxoade health' novamente.")
        else:
            click.echo("Comando abortado.")
        return False
    return True

def _run_all_analyses(path, ignore, complexity_threshold, min_coverage):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo encontrar arquivos e executar as análises de complexidade e cobertura.
    config = _load_config()
    final_ignore_list = list(set(config.get('ignore', []) + ignore))
    folders_to_ignore = set([item.lower() for item in final_ignore_list] + ['venv', 'build', 'dist', '.git'])
    
    files_to_check = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))

    all_findings = []
    all_findings.extend(_analyze_complexity(path, files_to_check, complexity_threshold))
    all_findings.extend(_analyze_test_coverage(path, min_coverage))
    return all_findings

def _handle_dependency_errors(ctx, path, logger):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo verificar se os únicos erros são de dependências e solicitar a configuração.
    summary = logger.results.get('summary', {})
    if summary.get('errors', 0) > 0:
        dep_errors = [f for f in logger.results.get('findings', []) if f.get('type') == 'ERROR' and ('não está instalada' in f.get('message', '') or 'não encontrado' in f.get('message', ''))]
        if len(dep_errors) == summary.get('errors', 0):
            click.echo(Fore.YELLOW + "\n[AVISO] A análise encontrou erros de dependência.")
            if click.confirm(Fore.CYAN + "Deseja executar 'doxoade setup-health' para instalar as dependências corretas?"):
                setup_health_command = ctx.parent.get_command(ctx, 'setup-health')
                ctx.invoke(setup_health_command, path=path)
                click.echo(Fore.CYAN + Style.BRIGHT + "\nConfiguração concluída. Por favor, execute 'doxoade health' novamente.")
            return False
    return True

def _analyze_complexity(project_path, files_to_check, threshold):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo analisar a complexidade ciclomática.
    try:
        from radon.visitors import ComplexityVisitor
    except ImportError:
        return [{'type': 'error', 'message': "A biblioteca 'radon' não está instalada.", 'details': "Execute 'doxoade setup-health' para instalar."}]

    findings = []
    config = _load_config()
    source_dir = config.get('source_dir', '.')
    source_path = os.path.abspath(os.path.join(project_path, source_dir))
    relevant_files = [f for f in files_to_check if os.path.abspath(f).startswith(source_path)]
    
    for file_path in relevant_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            visitor = ComplexityVisitor.from_code(content)
            for func in visitor.functions:
                if func.complexity > threshold:
                    findings.append({
                        'type': 'warning',
                        'message': f"Função '{func.name}' tem complexidade alta ({func.complexity}).",
                        'details': f"O máximo recomendado é {threshold}.",
                        'file': file_path,
                        'line': func.lineno
                    })
        except Exception:
            continue
            
    return findings
    
def _analyze_test_coverage(project_path, min_coverage):
    #2025/10/11 - 33.0(Ver), 1.0(Fnc). Função movida para plugin.
    #A função tem como objetivo analisar a cobertura de testes.
    try:
        from importlib import util as importlib_util
    except ImportError:
        return [{'type': 'error', 'message': "Módulo 'importlib' não encontrado."}]

    if not importlib_util.find_spec("coverage") or not importlib_util.find_spec("pytest"):
        return [{'type': 'error', 'message': "As bibliotecas 'coverage' ou 'pytest' não estão instaladas.", 'details': "Execute 'doxoade setup-health' para instalar."}]

    findings = []
    config = _load_config()
    source_dir = config.get('source_dir', '.')
    venv_python = _get_venv_python_executable()
    if not venv_python:
        return [{'type': 'error', 'message': "Não foi possível encontrar o executável Python do venv."}]

    run_tests_cmd = [venv_python, '-m', 'coverage', 'run', f'--source={source_dir}', '-m', 'pytest']
    generate_report_cmd = [venv_python, '-m', 'coverage', 'json']

    original_dir = os.getcwd()
    try:
        os.chdir(project_path)
        test_result = subprocess.run(run_tests_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if test_result.returncode != 0:
            if "no tests ran" in test_result.stdout or "collected 0 items" in test_result.stdout:
                return [{'type': 'warning', 'message': "Nenhum teste foi encontrado pelo pytest."}]
            else:
                return [{'type': 'error', 'message': "A suíte de testes falhou.", 'details': f"Saída do Pytest:\n{test_result.stdout}\n{test_result.stderr}"}]

        subprocess.run(generate_report_cmd, capture_output=True, check=True)

        if os.path.exists('coverage.json'):
            with open('coverage.json', 'r') as f: report_data = json.load(f)
            total_coverage = report_data['totals']['percent_covered']
            if total_coverage < min_coverage:
                findings.append({'type': 'warning', 'message': f"Cobertura de testes está baixa: {total_coverage:.2f}%.", 'details': f"O mínimo recomendado é {min_coverage}%.", 'file': project_path})
    finally:
        if os.path.exists('coverage.json'): os.remove('coverage.json')
        if os.path.exists('.coverage'): os.remove('.coverage')
        os.chdir(original_dir)
        
    return findings