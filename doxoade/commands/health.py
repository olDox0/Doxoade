# doxoade/commands/health.py
import sys
import subprocess
import os
import json
import click
from colorama import Fore
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _present_results,
    _get_project_config
)

# Tenta importar Radon do ambiente do Doxoade (Batteries Included)
try:
    from radon.visitors import ComplexityVisitor
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

@click.command('health')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text')
@click.option('--complexity-threshold', default=15, help="Nível de complexidade.", type=int)
@click.option('--min-coverage', default=70, help="Cobertura de testes mínima.", type=int)
def health(ctx, path, ignore, output_format, complexity_threshold, min_coverage):
    """Mede a qualidade do código (complexidade e cobertura de testes)."""
    arguments = {k: v for k, v in locals().items() if k != 'ctx'}
    
    with ExecutionLogger('health', path, arguments) as logger:
        if output_format == 'text': click.echo(Fore.CYAN + "[HEALTH] Iniciando check-up do projeto...")

        # 1. Análise Estática (Radon) - Usa ambiente do Doxoade
        findings = _analyze_complexity(path, list(ignore), complexity_threshold)
        
        # 2. Análise Dinâmica (Coverage) - Precisa do venv do USUÁRIO
        # Se o usuário não tem venv ou não tem coverage instalado, pulamos silenciosamente ou com aviso leve
        venv_python = _get_venv_python_executable(path)
        if venv_python:
            coverage_findings = _analyze_test_coverage(path, venv_python, min_coverage)
            findings.extend(coverage_findings)
        else:
            if output_format == 'text': 
                click.echo(Fore.YELLOW + "   > [SKIP] Coverage pulado (venv do projeto não detectado).")

        # 3. Análise de Dependências
        findings.extend(_analyze_requirements_quality(path))

        for f in findings:
            logger.add_finding(
                f.get('severity', 'WARNING'), 
                f.get('message', 'Mensagem ausente'), 
                details=f.get('details'), 
                file=f.get('file'), 
                line=f.get('line')
            )

        _present_results(output_format, logger.results)
        
        if logger.results['summary'].get('critical', 0) > 0:
            sys.exit(1)

def _analyze_complexity(project_path, ignore, threshold):
    """Analisa a complexidade ciclomática usando o Radon do Doxoade."""
    if not RADON_AVAILABLE:
        return [{'severity': 'WARNING', 'message': "Radon não encontrado no Doxoade. Instale 'doxoade' completo."}]

    findings = []
    # Lógica de coleta simplificada (usa os ignores)
    config = _get_project_config(None, start_path=project_path)
    config_ignore = [item.strip('/') for item in config.get('ignore', [])]
    folders_to_ignore = set([item.lower() for item in config_ignore + ignore] + ['venv', 'build', 'dist', '.git', '__pycache__'])

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    visitor = ComplexityVisitor.from_code(content)
                    for func in visitor.functions:
                        if func.complexity > threshold:
                            findings.append({
                                'severity': 'WARNING', 
                                'message': f"Função '{func.name}' muito complexa ({func.complexity}).", 
                                'details': f"Limite é {threshold}. Considere refatorar.", 
                                'file': file_path, 
                                'line': func.lineno
                            })
                except Exception: pass
    return findings

def _analyze_test_coverage(project_path, venv_python, min_coverage):
    """
    Tenta rodar coverage no venv do usuário.
    Se falhar (ferramenta não instalada), avisa mas não quebra.
    """
    # Verifica se coverage está instalado no venv DO USUÁRIO
    try:
        subprocess.run([venv_python, '-m', 'coverage', '--version'], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return [{'severity': 'INFO', 'message': "Ferramenta 'coverage' não instalada no projeto. Testes pulados."}]

    # Roda os testes
    try:
        # Usa module coverage run para garantir que usa o coverage do venv
        cmd = [venv_python, '-m', 'coverage', 'run', '-m', 'pytest', '-q']
        subprocess.run(cmd, cwd=project_path, capture_output=True, check=True) 
        
        # Gera relatório JSON
        subprocess.run([venv_python, '-m', 'coverage', 'json'], cwd=project_path, capture_output=True, check=True)
        
        json_path = os.path.join(project_path, 'coverage.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            # Limpa o arquivo JSON após ler
            os.remove(json_path)
            
            percent = data.get('totals', {}).get('percent_covered', 0)
            
            if percent < min_coverage:
                return [{'severity': 'WARNING', 'message': f"Cobertura de testes baixa: {percent:.1f}% (Meta: {min_coverage}%)"}]
            else:
                # Se a cobertura for boa, não retorna erro, mas poderiamos retornar INFO
                pass
                
    except Exception:
        # Falhas na execução dos testes não devem crashar o health check, apenas avisar
        return [{'severity': 'WARNING', 'message': "Falha ao executar suite de testes para cobertura (verifique 'doxoade test')."}]
    
    return []

def _analyze_requirements_quality(project_path):
    """Analisa o requirements.txt em busca de boas práticas (pinagem de versão)."""
    findings = []
    requirements_file = os.path.join(project_path, 'requirements.txt')
    if not os.path.exists(requirements_file):
        return findings

        CRITICAL_PACKAGES = {'numpy', 'packaging', 'click', 'rich'}
        #HEAVY_PACKAGES_WARNING = {'pandas', 'torch', 'tensorflow', 'scikit-learn', 'lxml'}
    
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'): continue
            
            # Verifica pacotes críticos sem '=='
            if any(pkg in line.lower() for pkg in CRITICAL_PACKAGES) and '==' not in line:
                # Extrai nome do pacote
                pkg_name = line.split('>')[0].split('<')[0].split('~')[0].strip()
                if pkg_name in CRITICAL_PACKAGES:
                    findings.append({
                        'severity': 'WARNING',
                        'message': f"Pacote crítico '{pkg_name}' sem versão fixada (==).",
                        'details': "Projetos estáveis devem pinar versões de bibliotecas principais.",
                        'file': 'requirements.txt',
                        'line': i + 1
                    })
    except IOError: pass
    return findings