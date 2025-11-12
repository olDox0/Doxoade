# doxoade/commands/health.py
# atualizado em 2025/10/25 - Versão do projeto 43(Ver), Versão da função 8.0(Fnc).
#Descrição: Esta função é refatorada para robustez. Ela agora usa o método seguro .get('key', 0) para acessar os contadores de "findings", prevenindo um KeyError em execuções sem resultados. Além disso, a lógica de sys.exit(1) foi corrigida para ser acionada apenas por erros críticos, e não por avisos.
#O que poderia ser melhorado: A função _run_all_analyses poderia ser dividida em funções menores para reduzir sua complexidade.

import sys
import subprocess
#import shutil
import os
import json
import click
#import re
from colorama import Fore

# --- Imports Corretos e Finais de shared_tools ---
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _present_results,
    _get_project_config # A ÚNICA função de configuração necessária
)

@click.command('health')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--complexity-threshold', default=15, help="Nível de complexidade.", type=int)
@click.option('--min-coverage', default=70, help="Cobertura de testes mínima.", type=int)
def health(ctx, path, ignore, output_format, complexity_threshold, min_coverage):
    """Mede a qualidade do código (complexidade e cobertura de testes)."""
    arguments = {k: v for k, v in locals().items() if k != 'ctx'}
    
    with ExecutionLogger('health', path, arguments) as logger:
        if output_format == 'text': click.echo(Fore.YELLOW + "[HEALTH] Executando análise de saúde do projeto...")

        if not _get_venv_python_executable():
             logger.add_finding('CRITICAL', "Projeto sem 'venv' configurado.", details="Execute 'doxoade doctor' para reparar.")
             _present_results(output_format, logger.results)
             sys.exit(1)

        findings = _run_all_analyses(path, list(ignore), complexity_threshold, min_coverage, logger)
        for f in findings:
            # CORREÇÃO: Usa .get() para acesso seguro, embora já fosse seguro.
            logger.add_finding(f.get('severity', 'WARNING'), f.get('message', 'Mensagem ausente'), details=f.get('details'), file=f.get('file'), line=f.get('line'))

        _present_results(output_format, logger.results)
        
        # --- CORREÇÃO DE PONTOS DE RISCO ---
        summary = logger.results.get('summary', {})
        critical_count = summary.get('critical', 0)
        error_count = summary.get('errors', 0)
        
        if critical_count > 0 or error_count > 0:
            sys.exit(1)

def _run_all_analyses(project_path, ignore, complexity_threshold, min_coverage, logger):
    """Orquestra as análises de complexidade e cobertura."""
    config = _get_project_config(logger)
    if not config.get('search_path_valid'):
        return []

    search_path = config.get('search_path')
    source_dir_relative = config.get('source_dir', '.')
    
    config_ignore = [item.strip('/') for item in config.get('ignore', [])]
    folders_to_ignore = set([item.lower() for item in config_ignore + ignore] + ['venv', 'build', 'dist', '.git', 'tests'])
    
    files_to_check = []
    for root, dirs, files in os.walk(search_path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))

    all_findings = []
    all_findings.extend(_analyze_complexity(files_to_check, complexity_threshold))
    all_findings.extend(_analyze_test_coverage(project_path, min_coverage, source_dir_relative))
    all_findings.extend(_analyze_requirements_quality(project_path))
    return all_findings

def _analyze_complexity(files_to_check, threshold):
    """Analisa a complexidade ciclomática dos arquivos fornecidos."""
    try:
        from radon.visitors import ComplexityVisitor
    except ImportError:
        return [{'severity': 'ERROR', 'message': "A biblioteca 'radon' não está instalada."}]

    findings = []
    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if not content.strip(): continue
            visitor = ComplexityVisitor.from_code(content)
            for func in visitor.functions:
                if func.complexity > threshold:
                    findings.append({'severity': 'WARNING', 'message': f"Função '{func.name}' tem complexidade alta ({func.complexity}).", 'details': f"Máximo: {threshold}.", 'file': file_path, 'line': func.lineno})
        except Exception:
            continue
    return findings
    
def _execute_coverage_run(venv_python, source_dir):
    """Executa o pytest via coverage e retorna o resultado do processo."""
    run_tests_cmd = [venv_python, '-m', 'coverage', 'run', f'--source={source_dir}', '-m', 'pytest', '-p', 'no:cache']
    return subprocess.run(run_tests_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

def _generate_and_parse_coverage_report(venv_python, min_coverage, project_path):
    """Gera o relatório JSON do coverage e o analisa."""
    generate_report_cmd = [venv_python, '-m', 'coverage', 'json']
    subprocess.run(generate_report_cmd, capture_output=True, check=True, encoding='utf-8')

    if os.path.exists('coverage.json'):
        with open('coverage.json', 'r') as f:
            report_data = json.load(f)
        total_coverage = report_data.get('totals', {}).get('percent_covered', 0)
        if total_coverage < min_coverage:
            return [{'severity': 'WARNING', 'message': f"Cobertura de testes está baixa: {total_coverage:.2f}%.", 'details': f"Mínimo: {min_coverage}%.", 'file': project_path}]
    return []

def _analyze_test_coverage(project_path, min_coverage, source_dir):
    """(Orquestrador) Analisa a cobertura de testes do projeto."""
    try:
        from importlib import util as importlib_util
    except ImportError:
        return [{'severity': 'ERROR', 'message': "Módulo 'importlib' não encontrado."}]

    if not all(importlib_util.find_spec(pkg) for pkg in ["coverage", "pytest"]):
        return [{'severity': 'ERROR', 'message': "As bibliotecas 'coverage' ou 'pytest' não estão instaladas."}]

    venv_python = _get_venv_python_executable()
    if not venv_python:
        return [{'severity': 'ERROR', 'message': "Não foi possível encontrar o executável Python do venv."}]

    original_dir = os.getcwd()
    try:
        os.chdir(project_path)
        
        test_result = _execute_coverage_run(venv_python, source_dir)
        
        # 5 = no tests collected, que não é um erro fatal.
        if test_result.returncode != 0 and test_result.returncode != 5:
            return [{'severity': 'ERROR', 'message': "A suíte de testes falhou.", 'details': f"Saída do Pytest:\n{test_result.stdout}\n{test_result.stderr}"}]
        
        if "no tests ran" in test_result.stdout or "collected 0 items" in test_result.stdout:
            return [{'severity': 'WARNING', 'message': "Nenhum teste foi encontrado pelo pytest."}]

        return _generate_and_parse_coverage_report(venv_python, min_coverage, project_path)

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return [{'severity': 'ERROR', 'message': "Falha ao executar o coverage ou pytest.", 'details': str(e)}]
    finally:
        if os.path.exists('coverage.json'): os.remove('coverage.json')
        if os.path.exists('.coverage'): os.remove('.coverage')
        os.chdir(original_dir)
    
def _analyze_requirements_quality(project_path):
    """Analisa o requirements.txt em busca de boas práticas."""
    findings = []
    requirements_file = os.path.join(project_path, 'requirements.txt')
    if not os.path.exists(requirements_file):
        return findings

    # Pacotes críticos que frequentemente causam problemas de ABI se não forem pinados.
    CRITICAL_PACKAGES = {'numpy', 'torch', 'tensorflow', 'pandas', 'scikit-learn'}
    
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Verifica se a linha contém um dos pacotes críticos
            # e se NÃO contém '=='
            if any(pkg in line for pkg in CRITICAL_PACKAGES) and '==' not in line:
                package_name = line.split(">=")[0].split("<=")[0].split("~=")[0].strip()
                if package_name in CRITICAL_PACKAGES:
                    findings.append({
                        'severity': 'WARNING',
                        'message': f"Pacote crítico '{package_name}' não possui versão exata (==) fixada.",
                        'details': "Em projetos de ML, é crucial fixar versões de pacotes como numpy/torch para garantir a estabilidade do ambiente.",
                        'file': requirements_file,
                        'line': i + 1
                    })
    except IOError:
        pass # Ignora erros de leitura, pois o arquivo é opcional.
        
    return findings