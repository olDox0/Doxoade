import ast
import json
import configparser
import esprima
import os, sys, re
import shutil
import subprocess
import click
import shlex
import fnmatch
import tempfile
import traceback
from functools import wraps
from bs4 import BeautifulSoup
from io import StringIO
from colorama import init, Fore, Style
from pyflakes import api as pyflakes_api
from pathlib import Path
from datetime import datetime, timezone

# Inicializa o colorama para funcionar no Windows
init(autoreset=True)

#atualizado em 2025/09/28-Versão 14.0. Implementada a classe ExecutionLogger para um sistema de logging centralizado e robusto.
class ExecutionLogger:
    """Um gerenciador de contexto para registrar a execução de um comando doxoade."""
    def __init__(self, command_name, path, arguments):
        self.command_name = command_name
        self.path = path
        self.arguments = arguments
        self.results = {
            'summary': {'errors': 0, 'warnings': 0},
            'findings': []
        }

    def add_finding(self, f_type, message, file=None, line=None, details=None):
        """Adiciona um novo achado (erro ou aviso) ao log."""
        finding = {'type': f_type.upper(), 'message': message}
        if file: finding['file'] = file
        if line: finding['line'] = line
        if details: finding['details'] = details
        
        self.results['findings'].append(finding)
        
        if f_type == 'error':
            self.results['summary']['errors'] += 1
        elif f_type == 'warning':
            self.results['summary']['warnings'] += 1

    def __enter__(self):
        # Quando o bloco 'with' começa, ele retorna o próprio objeto logger.
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Quando o bloco 'with' termina, este método é chamado automaticamente.
        
        # Se uma exceção ocorreu, a registramos como um erro fatal.
        if exc_type:
            self.add_finding(
                'fatal_error',
                'A Doxoade encontrou um erro fatal interno durante a execução deste comando.',
                details=str(exc_val),
            )
            # Adicionamos o traceback ao último finding para diagnóstico completo.
            self.results['findings'][-1]['traceback'] = traceback.format_exc()

        # Independentemente do que aconteceu, escrevemos o estado final no log.
        _log_execution(self.command_name, self.path, self.results, self.arguments)

# -----------------------------------------------------------------------------
# GRUPO PRINCIPAL E CONFIGURAÇÃO
# -----------------------------------------------------------------------------

#atualizado em 2025/09/26-Versão 10.8. Adicionado tratamento de exceção global para garantir que falhas internas da ferramenta sejam sempre registradas no log.
@click.group()
def cli():
    """olDox222 Advanced Development Environment (doxoade) LITE v1.0"""
    # Este é o ponto de entrada principal.
    # Envolvemos tudo em um try/except para capturar erros fatais da própria ferramenta.
    try:
        pass # A mágica do click acontece após esta função
    except Exception as e:
        # Se qualquer comando falhar com uma exceção não tratada, nós a registramos.
        results = {
            'summary': {'errors': 1, 'warnings': 0},
            'internal_error': [{
                'type': 'error',
                'message': 'A Doxoade encontrou um erro fatal interno.',
                'details': str(e),
                'traceback': traceback.format_exc()
            }]
        }
        _log_execution(command_name="FATAL", path=".", results=results, arguments={})
        # E então deixamos o erro acontecer para que o usuário o veja.
        raise e

#atualizado em 2025/09/27-Versão 13.1 (Final). Decorador de log corrigido para lidar com todos os tipos de comandos e argumentos de forma robusta, eliminando o IndexError.
def log_command_execution(func):
    """
    Decorador que envolve um comando click para garantir que sua execução
    e seus argumentos sejam sempre registrados no log.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # A forma mais robusta de obter o contexto é através do click.get_current_context()
        ctx = click.get_current_context()
        command_name = ctx.command.name
        
        # O caminho do projeto é geralmente o argumento 'path', mas usamos '.' como um padrão seguro.
        path = kwargs.get('path', '.')
        
        results = {'summary': {'errors': 0, 'warnings': 0}}
        try:
            # Executa o comando original, passando os argumentos exatamente como foram recebidos.
            return func(*args, **kwargs)
        except Exception:
            # O erro fatal já será capturado pelo nosso handler global.
            raise
        finally:
            # Usamos kwargs para registrar os argumentos, que contêm os parâmetros nomeados.
            _log_execution(command_name, path, results, kwargs)
            
    return wrapper

def _load_config():
    """Procura e carrega configurações de um arquivo .doxoaderc."""
    config = configparser.ConfigParser()
    config.read('.doxoaderc')
    settings = {'ignore': [], 'source_dir': '.'}
    if 'doxoade' in config:
        ignore_str = config['doxoade'].get('ignore', '')
        settings['ignore'] = [line.strip() for line in ignore_str.split('\n') if line.strip()]
        settings['source_dir'] = config['doxoade'].get('source_dir', '.') # Lê a nova configuração
    return settings

# -----------------------------------------------------------------------------
# COMANDOS DA CLI (ARQUITETURA FINAL E ROBUSTA)
# -----------------------------------------------------------------------------

#atualizado em 2025/09/24-Versão 8.0. Novo comando 'doctor' para meta-análise da própria ferramenta. Tem como função verificar o ambiente, as dependências internas e a qualidade do código da doxoade.
@cli.command()
@log_command_execution
def doctor():
    """Executa um diagnóstico completo da própria ferramenta doxoade."""
    click.echo(Fore.CYAN + Style.BRIGHT + "--- [DOCTOR] Executando diagnóstico da ferramenta Doxoade ---")

    findings = []
    # --- Verificação 1: Diagnóstico do PATH ---
    click.echo(Fore.YELLOW + "\n--- 1. Verificando o ambiente de instalação (PATH)... ---")
    try:
        result = subprocess.run(['where', 'doxoade'], capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        locations = result.stdout.strip().splitlines()
        if len(locations) > 1:
            findings.append({
                'type': 'error',
                'message': "Múltiplas instalações do 'doxoade' encontradas no seu PATH.",
                'details': "Isso pode causar conflitos. Encontrado em:\n" + "\n".join(f"   - {loc}" for loc in locations)
            })
        else:
            click.echo(Fore.GREEN + f"[OK] Instalação única encontrada em: {locations[0]}")
    except (FileNotFoundError, subprocess.CalledProcessError):
        findings.append({'type': 'error', 'message': "Não foi possível executar o comando 'where doxoade'.", 'details': "Isso pode indicar um problema com a instalação ou com o PATH do sistema."  })
    
    # --- Verificação 2: Dependências Internas ---
    click.echo(Fore.YELLOW + "\n--- 2. Verificando as dependências internas da Doxoade... ---")
    doxoade_path = _get_doxoade_installation_path()
    if doxoade_path:
        doxoade_reqs = os.path.join(doxoade_path, 'requirements.txt')
        if os.path.exists(doxoade_reqs):
            try:
                # Usamos o pip do venv da doxoade para checar suas próprias dependências
                doxoade_venv_python = os.path.join(doxoade_path, 'venv', 'Scripts', 'python')
                cmd = [doxoade_venv_python, '-m', 'pip', 'check']
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
                click.echo(Fore.GREEN + "[OK] Todas as dependências internas estão corretamente instaladas.")
            except Exception:
                findings.append({'type': 'error', 'message': "Verificação de dependências internas falhou.", 'details': "Execute 'pip check' no venv da doxoade para mais detalhes."})
        else:
            findings.append({'type': 'warning', 'message': "Arquivo 'requirements.txt' da doxoade não encontrado."})
    else:
        findings.append({'type': 'error', 'message': "Não foi possível localizar o diretório de instalação da doxoade."})

    # --- Verificação 3: Auto-Diagnóstico de Qualidade ---
    click.echo(Fore.YELLOW + "\n--- 3. Executando auto-diagnóstico de qualidade (dogfooding)... ---")
    if doxoade_path:
        os.chdir(doxoade_path)
        cmd = [sys.executable, '-m', 'doxoade.doxoade', 'check', '.']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            click.echo(Fore.GREEN + "[OK] O código-fonte da Doxoade passou em seu próprio teste de qualidade ('check').")
        else:
            findings.append({'type': 'warning', 'message': "A Doxoade encontrou problemas de qualidade em seu próprio código.", 'details': f"Execute 'doxoade check .' no diretório da ferramenta   para ver os detalhes:\n{result.stdout}"})
        
    # --- Sumário Final ---
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
    if not findings:
        click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] A sua instalação da Doxoade parece estar saudável e pronta para uso!")
    else:
        click.echo(Fore.RED + Style.BRIGHT + f"[ATENÇÃO] Foram encontrados {len(findings)} problemas:")
        for finding in findings:
            color = Fore.RED if finding['type'] == 'error' else Fore.YELLOW
            tag = '[ERRO]' if finding['type'] == 'error' else '[AVISO]'
            click.echo(color + f"{tag} {finding['message']}")
            if 'details' in finding:
                click.echo(Fore.CYAN + f"   > {finding['details']}")
        
def _get_doxoade_installation_path():
    """Encontra o caminho do diretório de instalação da própria ferramenta doxoade."""
    try:
        # __file__ aponta para o doxoade.py, então subimos dois níveis para chegar à raiz do projeto
        doxoade_script_path = os.path.abspath(__file__)
        doxoade_package_path = os.path.dirname(doxoade_script_path)
        doxoade_root_path = os.path.dirname(doxoade_package_path)
        # Verificamos se é um diretório de projeto válido procurando pelo setup.py
        if os.path.exists(os.path.join(doxoade_root_path, 'setup.py')):
            return doxoade_root_path
    except NameError:
        # __file__ não existe em alguns contextos, como em um executável congelado
        pass
    return None

#atualizado em 2025/09/25-Versão 9.1. Novo comando 'dashboard' para visualizar tendências de saúde do projeto a partir dos logs.
@cli.command()
@log_command_execution
@click.option('--project', default=None, help="Filtra o dashboard para um caminho de projeto específico.")
def dashboard(project):
    """Exibe um painel com a saúde e tendências dos projetos analisados."""

    log_file = Path.home() / '.doxoade' / 'doxoade.log'
    if not log_file.exists():
        click.echo(Fore.YELLOW + "Nenhum arquivo de log encontrado. Execute alguns comandos de análise primeiro."); return

    click.echo(Fore.CYAN + Style.BRIGHT + "--- [DASHBOARD] Painel de Saúde de Engenharia ---")

    entries = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                # Filtra pelo projeto, se especificado
                if project and os.path.abspath(project) != entry.get('project_path'):
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    if not entries:
        click.echo(Fore.RED + "Nenhuma entrada de log encontrada para o filtro especificado."); return

    # --- Análise 1: Tendência de Erros ao Longo do Tempo ---
    errors_by_day = {}
    for entry in entries:
        day = entry['timestamp'][:10] # Pega apenas a data YYYY-MM-DD
        errors = entry['summary'].get('errors', 0)
        errors_by_day[day] = errors_by_day.get(day, 0) + errors

    click.echo(Fore.YELLOW + "\n--- Tendência de Erros (últimos 7 dias) ---")
    sorted_days = sorted(errors_by_day.keys())[-7:]
    max_errors = max(errors_by_day.values()) if errors_by_day else 1
    for day in sorted_days:
        count = errors_by_day[day]
        bar_length = int((count / max_errors) * 40) if max_errors > 0 else 0
        bar = '█' * bar_length
        click.echo(f"{day} | {bar} ({count} erros)")

    # --- Análise 2: Projetos com Mais Problemas ---
    errors_by_project = {}
    for entry in entries:
        proj_name = os.path.basename(entry['project_path'])
        errors = entry['summary'].get('errors', 0)
        errors_by_project[proj_name] = errors_by_project.get(proj_name, 0) + errors

    click.echo(Fore.YELLOW + "\n--- Projetos com Mais Erros Registrados ---")
    sorted_projects = sorted(errors_by_project.items(), key=lambda item: item[1], reverse=True)[:5]
    for proj, count in sorted_projects:
        click.echo(f" - {proj}: {count} erros")

    # --- Análise 3: Erros Mais Frequentes ---
    errors_by_type = {}
    for entry in entries:
        for finding in entry.get('findings', []):
            if finding['type'] == 'error':
                msg = finding['message'].split(':')[1].strip() if ':' in finding['message'] else finding['message']
                errors_by_type[msg] = errors_by_type.get(msg, 0) + 1
    
    click.echo(Fore.YELLOW + "\n--- Tipos de Erro Mais Frequentes ---")
    sorted_types = sorted(errors_by_type.items(), key=lambda item: item[1], reverse=True)[:5]
    for msg_type, count in sorted_types:
        click.echo(f" - {msg_type}: {count} ocorrências")

#atualizado em 2025/09/25-Versão 8.2. 'setup-health' agora verifica e cria o venv se ele não existir, tornando o comando mais robusto.
@cli.command('setup-health')
@log_command_execution
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
def setup_health(path):
    """Prepara um projeto para ser analisado pelo 'doxoade health'."""
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [SETUP-HEALTH] Configurando o projeto em '{path}' para análise de saúde ---")

    # --- Passo 0: Verificar e criar o venv, se necessário ---
    click.echo(Fore.YELLOW + "\n--- 0. Verificando ambiente virtual ('venv')... ---")
    venv_path = os.path.join(path, 'venv')
    if not os.path.exists(venv_path):
        click.echo(Fore.YELLOW + "   > Ambiente virtual não encontrado. Criando agora...")
        try:
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)
            click.echo(Fore.GREEN + "[OK] Ambiente virtual criado com sucesso.")
        except subprocess.CalledProcessError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao criar o ambiente virtual: {e.stderr.decode('utf-8', 'ignore')}")
            sys.exit(1)
    else:
        click.echo(Fore.GREEN + "[OK] Ambiente virtual já existe.")

    # --- Passo 1: Verificar e atualizar requirements.txt ---
    click.echo(Fore.YELLOW + "\n--- 1. Verificando 'requirements.txt'... ---")
    req_file = os.path.join(path, 'requirements.txt')
    health_deps = ['radon', 'coverage', 'pytest']
    deps_to_add = []
    
    if os.path.exists(req_file):
        with open(req_file, 'r', encoding='utf-8') as f:
            existing_deps = {line.strip().split('==')[0].lower() for line in f if line.strip() and not line.startswith('#')}
        
        for dep in health_deps:
            if dep not in existing_deps:
                deps_to_add.append(dep)
        
        if deps_to_add:
            with open(req_file, 'a', encoding='utf-8') as f:
                f.write('\n# Ferramentas de Análise de Saúde (adicionadas pelo doxoade)\n')
                for dep in deps_to_add:
                    f.write(f"{dep}\n")
            click.echo(Fore.GREEN + f"[OK] Adicionadas as seguintes dependências: {', '.join(deps_to_add)}")
        else:
            click.echo(Fore.GREEN + "[OK] Todas as dependências de saúde já estão no arquivo.")
    else:
        click.echo(Fore.YELLOW + "[AVISO] Arquivo 'requirements.txt' não encontrado. Criando um novo com as dependências de saúde.")
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write('# Ferramentas de Análise de Saúde (adicionadas pelo doxoade)\n')
            for dep in health_deps:
                f.write(f"{dep}\n")
        deps_to_add = health_deps

    # --- Passo 2: Verificar e atualizar .doxoaderc ---
    click.echo(Fore.YELLOW + "\n--- 2. Verificando '.doxoaderc'... ---")
    config_file = os.path.join(path, '.doxoaderc')
    config = configparser.ConfigParser()
    config.read(config_file)
    
    if 'doxoade' not in config:
        config['doxoade'] = {}

    current_source_dir = config['doxoade'].get('source_dir', '.')
    
    new_source_dir = click.prompt(
        "Qual é o diretório principal do seu código-fonte? (ex: ., src, nome_do_projeto)",
        default=current_source_dir
    )
    config['doxoade']['source_dir'] = new_source_dir
    
    with open(config_file, 'w', encoding='utf-8') as f:
        config.write(f)
    click.echo(Fore.GREEN + f"[OK] Arquivo '.doxoaderc' configurado com 'source_dir = {new_source_dir}'.")
    
    # --- Passo 3: Instalar dependências, se necessário ---
    if deps_to_add:
        click.echo(Fore.YELLOW + "\n--- 3. Instalando novas dependências... ---")
        venv_python = os.path.join(path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python')
        cmd = [venv_python, '-m', 'pip', 'install', '-r', req_file]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            click.echo(Fore.GREEN + "[OK] Dependências instaladas com sucesso!")
        except subprocess.CalledProcessError as e:
            click.echo(Fore.RED + "[ERRO] Falha ao instalar as dependências.")
            click.echo(Fore.CYAN + f"   > Saída do Pip: {e.stdout}{e.stderr}")
            sys.exit(1)
    
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Configuração Concluída! ---")
    click.echo(Fore.WHITE + "O projeto agora está pronto. Você pode executar 'doxoade health' a qualquer momento.")

#atualizado em 2025/09/26-Versão 10.3. Corrigido o loop infinito no 'health' com uma lógica de verificação de ambiente mais robusta e direta.
@cli.command()
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--complexity-threshold', default=10, help="Nível de complexidade a partir do qual um aviso é gerado.", type=int)
@click.option('--min-coverage', default=70, help="Porcentagem mínima de cobertura de testes aceitável.", type=int)
def health(ctx, path, ignore, format, complexity_threshold, min_coverage):
    """Analisa a 'saúde' do código com métricas de qualidade (complexidade e testes)."""
    
    # --- LÓGICA DE VERIFICAÇÃO FINAL E ROBUSTA ---
    # Primeiro, verificamos se o executável python do venv existe. Esta é a verificação mais fundamental.
    venv_scripts_path = os.path.join(path, 'venv', 'Scripts' if os.name == 'nt' else 'bin')
    python_exe = os.path.join(venv_scripts_path, 'python.exe')
    python_no_exe = os.path.join(venv_scripts_path, 'python')

    venv_python_path = None
    if os.path.exists(python_exe):
        venv_python_path = python_exe
    elif os.path.exists(python_no_exe):
        venv_python_path = python_no_exe
    
    # Se não encontrarmos o python do venv, o projeto não está pronto.
    if not venv_python_path:
        click.echo(Fore.YELLOW + "[AVISO] Este projeto não possui um ambiente virtual ('venv') configurado.")
        if click.confirm(Fore.CYAN + "Deseja executar 'doxoade setup-health' para configurá-lo automaticamente?"):
            ctx.invoke(setup_health, path=path)
            click.echo(Fore.CYAN + Style.BRIGHT + "\nConfiguração concluída. Por favor, execute 'doxoade health' novamente para ver o relatório.")
        else:
            click.echo("Comando abortado. Execute 'doxoade setup-health' manualmente para preparar este projeto.")
        return

    # --- Se o venv existe, o resto da análise nos dirá se as dependências estão faltando ---
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        if format == 'text': click.echo(Fore.YELLOW + f"[HEALTH] Executando 'doxoade health' no diretório '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config['ignore'] + list(ignore)))
        
        folders_to_ignore = set([item.lower() for item in final_ignore_list] + ['venv', 'build', 'dist', '.git'])
        files_to_check = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    files_to_check.append(os.path.join(root, file))

        results.update({
            'complexity': _analyze_complexity(path, files_to_check, complexity_threshold),
            'test_coverage': _analyze_test_coverage(path, min_coverage)
        })

        # --- NOVA VERIFICAÇÃO PÓS-ANÁLISE ---
        # Se a única coisa que encontramos foi um erro de dependência, acionamos o setup.
        is_only_dep_error = False
        if results['summary']['errors'] > 0:
            dep_errors = [f for f in results.get('test_coverage', []) + results.get('complexity', []) if f['type'] == 'error']
            if len(dep_errors) == results['summary']['errors']:
                is_only_dep_error = True

        if is_only_dep_error:
            click.echo(Fore.YELLOW + "\n[AVISO] A análise encontrou erros de dependência (ex: 'radon' ou 'coverage' não instalados).")
            if click.confirm(Fore.CYAN + "Deseja executar 'doxoade setup-health' para instalar as dependências corretas?"):
                ctx.invoke(setup_health, path=path)
                click.echo(Fore.CYAN + Style.BRIGHT + "\nConfiguração concluída. Por favor, execute 'doxoade health' novamente para ver o relatório.")
            else:
                click.echo("Comando abortado.")
            return


        _update_summary_from_findings(results)
        _present_results(format, results)
    
    except Exception as e:
        safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        click.echo(Fore.RED + f"\n[ERRO FATAL] O 'health check' falhou inesperadamente: {safe_error}", err=True)
        results['summary']['errors'] += 1
    finally:
        _log_execution(command_name='health', path=path, results=results, arguments={"ignore": list(ignore), "format": format})
        if results['summary']['errors'] > 0 and not is_only_dep_error:
            sys.exit(1)

#atualizado em 2025/09/27-Versão 12.2 (PoC). Novo comando 'apicheck' para análise estática de uso de APIs. Tem como função ler um 'apicheck.json' e verificar se as chamadas de API no código seguem as regras do contrato.
@cli.command('apicheck')
@log_command_execution
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
def apicheck(path, ignore):
    """Analisa o uso de APIs com base em um arquivo de contrato 'apicheck.json'."""
    results = {'summary': {'errors': 0, 'warnings': 0}}
    click.echo(Fore.YELLOW + f"[APICHECK] Executando análise de contratos de API em '{path}'...")
    
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        # --- Passo 1: Carregar o Contrato ---
        contract_file = os.path.join(path, 'apicheck.json')
        if not os.path.exists(contract_file):
            click.echo(Fore.YELLOW + "[AVISO] Arquivo 'apicheck.json' não encontrado. Nenhuma análise será feita.")
            return
    
        try:
            with open(contract_file, 'r', encoding='utf-8') as f:
                contracts = json.load(f).get('contracts', [])
        except (json.JSONDecodeError, IOError) as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao ler ou decodificar 'apicheck.json': {e}")
            sys.exit(1)
    
        # --- Passo 2: Encontrar Arquivos e Analisar ---
        config = _load_config()
        final_ignore_list = list(set(config['ignore'] + list(ignore)))
        folders_to_ignore = set([item.lower() for item in final_ignore_list] + ['venv', 'build', 'dist', '.git'])
        files_to_check = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    files_to_check.append(os.path.join(root, file))
    
        api_findings = []
        for file_path in files_to_check:
            api_findings.extend(_analyze_api_calls(file_path, contracts))
            
        results['api_contracts'] = api_findings
        _update_summary_from_findings(results)
        _present_results('text', results)
    
        _log_execution('apicheck', path, results, {'ignore': list(ignore)})
        if results['summary']['errors'] > 0:
            sys.exit(1)
    finally:
        args = {"ignore": list(ignore)}
        _log_execution('apicheck', path, results, args)

#atualizado em 2025/09/28-Versão 13.4 (PoC). Novo comando 'deepcheck' para análise profunda de fluxo de funções. Tem como função mapear entradas, saídas e pontos de risco lógico (ex: acesso inseguro a dicionários) usando AST.
@cli.command('deepcheck')
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--func', 'func_name', default=None, help="Analisa profundamente uma função específica.")
def deepcheck(file_path, func_name):
    """Executa uma análise profunda do fluxo de dados e pontos de risco em um arquivo Python."""
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [DEEPCHECK] Analisando fluxo de '{file_path}' ---")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
    except (SyntaxError, IOError) as e:
        click.echo(Fore.RED + f"[ERRO] Falha ao ler ou analisar o arquivo: {e}"); sys.exit(1)

    function_dossiers = _analyze_function_flow(tree, content, func_name)

    if not function_dossiers:
        msg = "Nenhuma função encontrada."
        if func_name: msg = f"A função '{func_name}' não foi encontrada no arquivo."
        click.echo(Fore.YELLOW + msg); return

    # --- Apresentação do Relatório ---
    for dossier in function_dossiers:
        header_color = Fore.RED if dossier['complexity_rank'] == 'Alta' else Fore.YELLOW if dossier['complexity_rank'] == 'Média' else Fore.WHITE
        click.echo(header_color + Style.BRIGHT + f"\n--- Função: '{dossier['name']}' (linha {dossier['lineno']}) ---")
        click.echo(f"  [Complexidade]: {dossier['complexity']} ({dossier['complexity_rank']})")

        click.echo(Fore.CYAN + "\n  [Entradas (Parâmetros)]")
        if not dossier['params']: click.echo("    - Nenhum parâmetro.")
        for p in dossier['params']: click.echo(f"    - Nome: {p['name']} (Tipo: {p['type']})")

        click.echo(Fore.CYAN + "\n  [Saídas (Pontos de Retorno)]")
        if not dossier['returns']: click.echo("    - Nenhum ponto de retorno explícito.")
        for r in dossier['returns']: click.echo(f"    - Linha {r['lineno']}: Retorna {r['type']}")

        click.echo(Fore.CYAN + "\n  [Pontos de Risco (Micro Análise de Erros)]")
        if not dossier['risks']: click.echo("    - Nenhum ponto de risco óbvio detectado.")
        for risk in dossier['risks']:
            click.echo(Fore.YELLOW + f"    - AVISO (Linha {risk['lineno']}): {risk['message']}")
            click.echo(Fore.WHITE + f"      > Detalhe: {risk['details']}")

#atualizado em 2025/09/28-Versão 13.5. Corrigido AttributeError no 'deepcheck' ao analisar parâmetros de função (arg.name -> arg.arg).
def _analyze_function_flow(tree, content, specific_func=None):
    """Usa AST para analisar o fluxo de dados e pontos de risco em funções."""
    dossiers = []
    try:
        from radon.visitors import ComplexityVisitor
    except ImportError:
        class ComplexityVisitor:
            def __init__(self, functions): self.functions = []
            @classmethod
            def from_code(cls, code): return cls([])
    
    visitor = ComplexityVisitor.from_code(content)
    complexity_map = {f.name: f.complexity for f in visitor.functions}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_name = node.name
            
            if specific_func and func_name != specific_func:
                continue

            params = []
            for arg in node.args.args:
                param_type = ast.unparse(arg.annotation) if arg.annotation else "não anotado"
                # --- A CORREÇÃO CRUCIAL ESTÁ AQUI ---
                params.append({'name': arg.arg, 'type': param_type}) # Corrigido de arg.name para arg.arg

            returns = []
            risks = []
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Return) and sub_node.value:
                    return_type = "um valor literal" if isinstance(sub_node.value, ast.Constant) else "uma variável" if isinstance(sub_node.value, ast.Name) else "o resultado de uma expressão/chamada"
                    returns.append({'lineno': sub_node.lineno, 'type': return_type})
                
                if isinstance(sub_node, ast.Subscript):
                    if isinstance(sub_node.slice, ast.Constant):
                        risks.append({
                            'lineno': sub_node.lineno,
                            'message': "Acesso a dicionário/lista sem tratamento de chave/índice.",
                            'details': f"O acesso direto a '{ast.unparse(sub_node)}' pode causar uma 'KeyError' ou 'IndexError'. Considere usar '.get()' para dicionários."
                        })

            complexity = complexity_map.get(func_name, 0)
            rank = "Alta" if complexity > 10 else "Média" if complexity > 5 else "Baixa"

            dossiers.append({
                'name': func_name,
                'lineno': node.lineno,
                'params': params,
                'returns': returns,
                'risks': risks,
                'complexity': complexity,
                'complexity_rank': rank
            })
            
    return dossiers

#atualizado em 2025/09/27-Versão 12.5 (Robusta). Motor do 'apicheck' completamente reescrito para ser mais simples e eficaz, corrigindo a falha na detecção de violações de contrato.
def _analyze_api_calls(file_path, contracts):
    """Usa AST para analisar um arquivo Python em busca de violações de contrato de API."""

    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        findings = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            return [] # Ignora arquivos com erro de sintaxe
    
        # Iteramos sobre todos os nós da árvore
        for node in ast.walk(tree):
            # Nosso alvo são apenas os nós de chamada de função
            if not isinstance(node, ast.Call):
                continue
    
            # Reconstruímos o nome completo da função (ex: 'requests.get')
            func_name_parts = []
            curr = node.func
            while isinstance(curr, ast.Attribute):
                func_name_parts.insert(0, curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                func_name_parts.insert(0, curr.id)
            full_func_name = ".".join(func_name_parts)
            
            # Verificamos se esta função corresponde a algum dos nossos contratos
            for contract in contracts:
                if contract.get('function') != full_func_name:
                    continue
    
                # --- Contrato Encontrado! Agora validamos as regras ---
                rules = contract.get('rules', {})
                provided_args = {kw.arg for kw in node.keywords}
    
                # Regra 1: required_params
                for param in rules.get('required_params', []):
                    if param not in provided_args:
                        findings.append({
                            'type': 'error',
                            'message': f"Chamada para '{full_func_name}' não possui o parâmetro obrigatório '{param}'.",
                            'details': f"Contrato '{contract['id']}' exige este parâmetro.",
                            'file': file_path,
                            'line': node.lineno
                        })
    
                # Regra 2: forbidden_params
                for param, bad_value in rules.get('forbidden_params', {}).items():
                    for kw in node.keywords:
                        # Verificamos se o argumento tem o valor proibido (ex: verify=False)
                        if kw.arg == param and isinstance(kw.value, ast.Constant) and kw.value.value == bad_value:
                            findings.append({
                                'type': 'error',
                                'message': f"Chamada para '{full_func_name}' usa o valor proibido '{param}={bad_value}'.",
                                'details': f"Contrato '{contract['id']}' proíbe este uso por razões de segurança.",
                                'file': file_path,
                                'line': node.lineno
                            })
                                
        return findings
    finally:
        _log_execution('_analyze_api_calls', ".", results, {'file_path': file_path, 'contracts': contracts})

#atualizado em 2025/09/24-Versão 7.5. Corrigido NameError na chamada da função e removido import não utilizado.
def _analyze_complexity(project_path, files_to_check, threshold):
    """Analisa a complexidade ciclomática, focando no diretório de código-fonte."""
    
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        findings = []
        config = _load_config()
        source_dir = config.get('source_dir', '.')
        
        try:
            from radon.visitors import ComplexityVisitor
        except ImportError:
            return [{'type': 'error', 'message': "A biblioteca 'radon' não está instalada.", 'details': "Adicione 'radon' ao seu requirements.txt e instale."}]
    
        source_path = os.path.abspath(os.path.join(project_path, source_dir))
        relevant_files = [f for f in files_to_check if os.path.abspath(f).startswith(source_path)]
        
        try:
            for file_path in relevant_files:
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
            pass
        return findings
    finally:
        _log_execution('_analyze_complexity', ".", results, {'project_path': project_path, 'files_to_check': files_to_check, 'threshold': threshold })
    
#atualizado em 2025/09/24-Versão 7.4. 'health' agora lê 'source_dir' do .doxoaderc para focar a análise de radon e coverage, tornando os resultados mais precisos.
def _analyze_test_coverage(project_path, min_coverage):
    """Executa a suíte de testes com coverage.py, focando no diretório de código-fonte."""
    
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        findings = []
        config = _load_config()
        # Usa o 'source_dir' do config, ou o diretório do projeto como padrão.
        source_dir = config.get('source_dir', '.')
    
        try:
            from importlib import util as importlib_util
        except ImportError:
            return [{'type': 'error', 'message': "Módulo 'importlib' não encontrado."}]
    
        if not importlib_util.find_spec("coverage"):
            return [{'type': 'error', 'message': "A biblioteca 'coverage' não está instalada.", 'details': "Adicione 'coverage' e 'pytest' ao seu requirements.txt."}]
    
        venv_scripts_path = os.path.join(project_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin')
        python_exe = os.path.join(venv_scripts_path, 'python.exe')
        python_no_exe = os.path.join(venv_scripts_path, 'python')
    
        if os.path.exists(python_exe): venv_python = python_exe
        elif os.path.exists(python_no_exe): venv_python = python_no_exe
        else: return [{'type': 'error', 'message': "Não foi possível encontrar o executável Python do venv."}]
    
        # --- LÓGICA APRIMORADA: Passamos o --source para o coverage ---
        run_tests_cmd = [venv_python, '-m', 'coverage', 'run', f'--source={source_dir}', '-m', 'pytest']
        generate_report_cmd = [venv_python, '-m', 'coverage', 'json']
    
        original_dir = os.getcwd()
        try:
            os.chdir(project_path)
            test_result = subprocess.run(run_tests_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if test_result.returncode != 0:
                if "no tests ran" in test_result.stdout or "collected 0 items" in test_result.stdout:
                    return [{'type': 'warning', 'message': "Nenhum teste foi encontrado pelo pytest.", 'details': "Verifique se seus arquivos de teste seguem o padrão 'test_*.py' ou '*_test.py'."}]
                else:
                    return [{'type': 'error', 'message': "A suíte de testes falhou durante a execução.", 'details': f"Saída do Pytest:\n{test_result.stdout}\n{test_result.stderr}"}]
    
            subprocess.run(generate_report_cmd, capture_output=True, check=True)
    
            if os.path.exists('coverage.json'):
                with open('coverage.json', 'r') as f: report_data = json.load(f)
                total_coverage = report_data['totals']['percent_covered']
                if total_coverage < min_coverage:
                    findings.append({'type': 'warning', 'message': f"Cobertura de testes está baixa: {total_coverage:.2f}%.", 'details': f"O mínimo recomendado é {min_coverage}%.", 'file': project_path})
        except Exception: pass
        finally:
            if os.path.exists('coverage.json'): os.remove('coverage.json')
            if os.path.exists('.coverage'): os.remove('.coverage')
            os.chdir(original_dir)
            
        return findings
    finally:
        args = {"min_coverage": min_coverage}
        _log_execution('_analyze_test_coverage', ".", results, {'project_path': project_path, 'args': args })

#atualizado em 2025/09/23-Versão 5.5. Tutorial completamente reescrito para incluir todos os comandos da suíte (sync, release, clean, git-clean, guicheck) e melhorar a clareza para novos usuários.
@cli.command()
@log_command_execution
def tutorial():
    """Exibe um guia passo a passo do workflow completo do doxoade."""

    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Guia Completo do Workflow Doxoade ---")
        click.echo(Fore.WHITE + "Este guia mostra como usar o doxoade para gerenciar um projeto do início ao fim.")
    
        # Passo 1: Criação e Publicação
        click.echo(Fore.YELLOW + "\n\n--- Passo 1: Crie e Publique seu Projeto ---")
        click.echo(Fore.GREEN + "   1. Use 'doxoade init' para criar a estrutura local do seu projeto.")
        click.echo(Fore.CYAN + '        $ doxoade init meu-projeto-tutorial\n')
        click.echo(Fore.GREEN + "   2. Depois, vá para o GitHub (ou similar), crie um repositório VAZIO e copie a URL.")
        click.echo(Fore.GREEN + "   3. Finalmente, use 'doxoade git-new' para fazer a conexão e o primeiro push.")
        click.echo(Fore.CYAN + '        $ cd meu-projeto-tutorial')
        click.echo(Fore.CYAN + '        $ doxoade git-new "Commit inicial do projeto" https://github.com/usuario/meu-projeto-tutorial.git\n')
        click.echo(Fore.WHITE + "   Seu projeto agora está online!")
    
        # Passo 2: O Ciclo de Desenvolvimento Diário
        click.echo(Fore.YELLOW + "\n\n--- Passo 2: O Ciclo de Desenvolvimento Diário ---")
        click.echo(Fore.GREEN + "   1. Ative o ambiente virtual para garantir o isolamento das dependências.")
        click.echo(Fore.CYAN + '        $ .\\venv\\Scripts\\activate\n')
        click.echo(Fore.GREEN + "   2. Escreva seu código, modifique arquivos, crie novas funcionalidades...")
        click.echo(Fore.CYAN + "        (venv) > ... programando ...\n")
        click.echo(Fore.GREEN + "   3. Quando estiver pronto, use 'doxoade save' para fazer um commit seguro. Ele verifica seu código antes de salvar.")
        click.echo(Fore.CYAN + '        (venv) > doxoade save "Implementada a classe Usuario"\n')
        click.echo(Fore.GREEN + "   4. Para manter seu repositório local e o remoto sempre alinhados, use 'doxoade sync'. Ele puxa as últimas alterações e empurra as suas.")
        click.echo(Fore.CYAN + '        (venv) > doxoade sync')
    
        # Passo 3: Análise e Qualidade de Código
        click.echo(Fore.YELLOW + "\n\n--- Passo 3: Análise e Qualidade de Código ---")
        click.echo(Fore.GREEN + "   A qualquer momento, use os comandos de análise para verificar a saúde do seu projeto:")
        click.echo(Fore.GREEN + "    - Para código Python (erros, bugs, estilo):")
        click.echo(Fore.CYAN + '        $ doxoade check\n')
        click.echo(Fore.GREEN + "    - Para código de frontend (HTML, CSS, JS):")
        click.echo(Fore.CYAN + '        $ doxoade webcheck\n')
        click.echo(Fore.GREEN + "    - Para código de interfaces gráficas com Tkinter:")
        click.echo(Fore.CYAN + '        $ doxoade guicheck')
    
        # Passo 4: Versionamento e Lançamentos
        click.echo(Fore.YELLOW + "\n\n--- Passo 4: Versionamento e Lançamentos (Releases) ---")
        click.echo(Fore.GREEN + "   Quando seu projeto atinge um marco importante (ex: v1.0), você cria uma 'release' para marcar aquela versão.")
        click.echo(Fore.CYAN + '        $ doxoade release v1.0.0 "Lançamento da primeira versão estável"\n')
        click.echo(Fore.WHITE + "   Isso cria uma 'tag' no seu Git, facilitando a organização e o versionamento.")
    
        # Passo 5: Ferramentas Utilitárias e Automação
        click.echo(Fore.YELLOW + "\n\n--- Passo 5: Ferramentas Utilitárias e Automação ---")
        click.echo(Fore.GREEN + "    - Para investigar problemas passados, use 'doxoade log'. A flag '--snippets' é muito útil.")
        click.echo(Fore.CYAN + '        $ doxoade log -n 3 --snippets\n')
        click.echo(Fore.GREEN + "    - Para limpar o projeto de arquivos de cache e build (ex: __pycache__, dist/):")
        click.echo(Fore.CYAN + '        $ doxoade clean\n')
        click.echo(Fore.GREEN + "    - Para 'higienizar' seu repositório caso você tenha acidentalmente commitado arquivos que deveriam ser ignorados (como a 'venv'):")
        click.echo(Fore.CYAN + '        $ doxoade git-clean\n')
        click.echo(Fore.GREEN + "    - Para rodar uma sequência de comandos de uma só vez, use 'doxoade auto'.")
        click.echo(Fore.CYAN + '        $ doxoade auto "doxoade check ." "doxoade run meus_testes.py"')
    
        click.echo(Fore.YELLOW + Style.BRIGHT + "\n--- Fim do Guia ---\n")
        click.echo(Fore.WHITE + "   Lembre-se: use a flag '--help' em qualquer comando para ver mais detalhes e opções. Ex: 'doxoade save --help'.\n")
    finally:
        _log_execution('tutorial', ".", results, {})

#atualizado em 2025/09/24-Versão 6.1. Aprimorada a lógica da simulação para demonstrar a falha do 'save' e o uso do '--force', tornando o aprendizado mais completo.
@cli.command('tutorial-simulation')
@log_command_execution
def tutorial_simulation():
    """Executa uma simulação interativa do workflow do doxoade em um ambiente seguro."""

    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Bem-vindo à Simulação do Doxoade ---")
        click.echo(Fore.WHITE + "Vamos executar o workflow completo em um 'sandbox' (ambiente seguro) temporário.")
        click.echo(Fore.WHITE + "Nenhum arquivo ou repositório real será modificado.")
        click.echo(Fore.YELLOW + "Pressione Enter a cada passo para continuar...")
        click.pause()
    
        original_dir = os.getcwd()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                sim_project_path = os.path.join(temp_dir, 'meu-projeto-simulado')
                fake_remote_path_str = os.path.join(temp_dir, 'fake_remote.git')
                fake_remote_url = Path(fake_remote_path_str).as_uri()
    
                click.echo(Fore.MAGENTA + f"\n[SIMULAÇÃO] Sandbox criado em: {temp_dir}")
    
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] Criando um repositório Git 'remoto' falso e seguro...")
                subprocess.run(['git', 'init', '--bare', fake_remote_path_str], capture_output=True, check=True)
                click.pause()
    
                click.echo(Fore.YELLOW + "\n--- Passo 1: Crie e Publique seu Projeto ---")
                os.chdir(temp_dir)
                _run_sim_command('doxoade init meu-projeto-simulado\n')
    
                os.chdir(sim_project_path)
                _run_sim_command(f'doxoade git-new "Commit inicial simulado" "{fake_remote_url}"\n')
    
                click.echo(Fore.YELLOW + "\n--- Passo 2: O Ciclo de Desenvolvimento Diário ---")
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] Vamos criar um novo arquivo para simular uma alteração...")
                with open("nova_feature.py", "w") as f:
                    f.write("print('Nova funcionalidade!')\n")
                click.echo(Fore.WHITE + "Arquivo 'nova_feature.py' criado.")
                click.pause()
                
                _run_sim_command('doxoade save "Adicionada nova feature"\n')
    
                # --- LÓGICA DE ENSINO APRIMORADA ---
                click.echo(Fore.MAGENTA + Style.BRIGHT + "\n[APRENDIZADO] O 'save' falhou! Isso é esperado.")
                click.echo(Fore.WHITE + "Ele falhou porque o 'doxoade check' detectou que não estamos em um ambiente virtual ('venv') ativado.")
                click.echo(Fore.WHITE + "Esta é a principal proteção do 'doxoade save'.")
                click.echo(Fore.WHITE + "Para a simulação, vamos usar a flag '--force' para ignorar este erro e continuar.")
                click.pause()
    
                _run_sim_command('doxoade save "Adicionada nova feature" --force')
                
                click.echo(Fore.MAGENTA + Style.BRIGHT + "\n[APRENDIZADO] Agora que o commit foi feito, vamos sincronizar com o 'remoto'.")
                click.pause()
    
                _run_sim_command('doxoade sync\n')
    
                click.echo(Fore.YELLOW + "\n--- Passo 3: Análise e Qualidade de Código ---")
                _run_sim_command('doxoade check\n')
    
                click.echo(Fore.YELLOW + "\n--- Passo 4: Versionamento e Lançamentos (Releases) ---")
                _run_sim_command('doxoade release v0.1.0-sim "Lançamento da primeira versão simulada"\n')
    
                click.echo(Fore.YELLOW + "\n--- Passo 5: Limpeza de Artefatos ---")
                os.makedirs("__pycache__", exist_ok=True)
                with open("__pycache__/temp.pyc", "w") as f: f.write("cache")
                _run_sim_command('doxoade clean --force\n')
    
            except Exception as e:
                click.echo(Fore.RED + Style.BRIGHT + f"\n[ERRO NA SIMULAÇÃO] A simulação falhou: {e}")
            finally:
                os.chdir(original_dir)
                click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Fim da Simulação ---")
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] O sandbox e todos os arquivos temporários foram destruídos.")
                click.echo(Fore.WHITE + "Seu sistema de arquivos está intacto. Agora você está pronto para usar o doxoade em projetos reais!")
    finally:
        _log_execution('tutorial_simulation', ".", results, {})

#atualizado em 2025/09/24-Versão 6.2. Novo comando 'tutorial-interactive' que exige que o usuário digite os comandos, melhorando o aprendizado prático.
@cli.command('tutorial-interactive')
@log_command_execution
def tutorial_interactive():
    """Executa uma simulação PRÁTICA onde VOCÊ digita os comandos."""

    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Bem-vindo ao Laboratório Prático Doxoade ---")
        click.echo(Fore.WHITE + "Nesta simulação, você irá digitar os comandos para aprender na prática.")
        click.echo(Fore.WHITE + "Se ficar preso, digite 'ajuda' ou 'hint' para ver a resposta.")
        click.echo(Fore.WHITE + "Digite 'sair' ou 'exit' para terminar a qualquer momento.")
        if not click.confirm(Fore.YELLOW + "Podemos começar?"):
            click.echo("Simulação cancelada."); return
    
        original_dir = os.getcwd()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                sim_project_path = os.path.join(temp_dir, 'meu-projeto-pratico')
                fake_remote_path_str = os.path.join(temp_dir, 'fake_remote.git')
                fake_remote_url = Path(fake_remote_path_str).as_uri()
    
                click.echo(Fore.MAGENTA + f"\n[SIMULAÇÃO] Sandbox seguro criado em: {temp_dir}")
                subprocess.run(['git', 'init', '--bare', fake_remote_path_str], capture_output=True, check=True)
                os.chdir(temp_dir)
    
                # --- Passo 1: Criação e Publicação ---
                click.echo(Fore.YELLOW + "\n--- Passo 1: Crie e Publique seu Projeto ---")
                if not _prompt_and_run_sim_command(
                    prompt="Primeiro, use 'doxoade init' para criar um projeto chamado 'meu-projeto-pratico'",
                    expected_command="doxoade init meu-projeto-pratico"
                ): return
                
                os.chdir(sim_project_path)
                if not _prompt_and_run_sim_command(
                    prompt=f"Ótimo! Agora publique o projeto no nosso 'remote' falso com a mensagem 'Meu primeiro commit'.\nA URL do remote é: {fake_remote_url}",
                    expected_command=f'doxoade git-new "Meu primeiro commit" "{fake_remote_url}"'
                ): return
    
                # --- Passo 2: O Ciclo de Desenvolvimento Diário ---
                click.echo(Fore.YELLOW + "\n--- Passo 2: O Ciclo de Desenvolvimento Diário ---")
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] Vou criar um novo arquivo para simular uma alteração...")
                with open("feature.py", "w") as f: f.write("print('hello world')\n")
                click.echo(Fore.WHITE + "Arquivo 'feature.py' criado.")
    
                if not _prompt_and_run_sim_command(
                    prompt="Agora, use o commit seguro para salvar o novo arquivo com a mensagem 'Adicionada feature'",
                    expected_command='doxoade save "Adicionada feature"'
                ): return
    
                if not _prompt_and_run_sim_command(
                    prompt="O 'save' falhou (como esperado!). Force o commit para ignorar o erro de ambiente.",
                    expected_command='doxoade save "Adicionada feature" --force'
                ): return
    
                if not _prompt_and_run_sim_command(
                    prompt="Excelente! Agora sincronize suas alterações com o repositório remoto.",
                    expected_command='doxoade sync'
                ): return
                
                click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Simulação Concluída com Sucesso! ---")
    
            except Exception as e:
                click.echo(Fore.RED + Style.BRIGHT + f"\n[ERRO NA SIMULAÇÃO] A simulação falhou: {e}")
            finally:
                os.chdir(original_dir)
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] O sandbox e todos os arquivos temporários foram destruídos.")
    finally:
        _log_execution('tutorial_interactive', ".", results, {})

def _prompt_and_run_sim_command(prompt, expected_command):
    """Pede ao usuário para digitar um comando, valida, e então o executa."""
    click.echo(Fore.GREEN + f"\nOBJETIVO: {prompt}")
    
    expected_parts = shlex.split(expected_command)

    while True:
        user_input = click.prompt(Fore.CYAN + "$")
        
        if user_input.lower() in ['sair', 'exit']:
            click.echo(Fore.YELLOW + "Simulação encerrada."); return False
            
        if user_input.lower() in ['ajuda', 'hint', 'help']:
            click.echo(Fore.YELLOW + f"O comando correto é: {expected_command}"); continue

        user_parts = shlex.split(user_input)

        # Lógica de validação flexível:
        # Para 'save', só verificamos os 3 primeiros componentes
        is_correct = False
        if expected_parts[1] == 'save' and len(user_parts) >= 3:
            is_correct = user_parts[:2] == expected_parts[:2]
        elif expected_parts[1] == 'git-new' and len(user_parts) >= 3:
             is_correct = user_parts[:2] == expected_parts[:2]
        else: # Validação estrita para outros comandos
            is_correct = user_parts == expected_parts

        if is_correct:
            click.echo(Fore.GREEN + "Correto!")
            break
        else:
            click.echo(Fore.RED + "Comando incorreto. Tente novamente ou digite 'ajuda'.")
    
    # Execução do comando
    click.echo(Fore.WHITE + Style.DIM + "--- Saída do Comando ---")
    python_executable = sys.executable
    command_to_run = [python_executable, '-m', 'doxoade.doxoade'] + user_parts[1:]
    
    process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    process.wait()
    click.echo(Fore.WHITE + Style.DIM + "--- Fim da Saída ---")
    return True

def _run_sim_command(command_str):
    """Função auxiliar para exibir, pausar e executar um comando na simulação."""
    click.echo(Fore.GREEN + "\nAgora, vamos executar o comando:")
    click.echo(Fore.CYAN + f'    $ {command_str}')
    click.pause()
    click.echo(Fore.WHITE + Style.DIM + "--- Saída do Comando ---")
    
    # Executa o comando doxoade usando o mesmo Python que está rodando a simulação
    python_executable = sys.executable
    args = shlex.split(command_str)
    command_to_run = [python_executable, '-m', 'doxoade.doxoade'] + args[1:]
    
    # Usamos Popen para streaming de saída em tempo real
    process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    
    for line in iter(process.stdout.readline, ''):
        print(line, end='') # A saída já vem com \n
    
    process.wait()
    click.echo(Fore.WHITE + Style.DIM + "--- Fim da Saída ---\n")
    

#atualizado em 2025/09/23-Versão 5.2. Adicionados comandos 'release' e 'sync' para completar a suíte Git. Tem como função automatizar o versionamento e a sincronização com o repositório remoto. Melhoria: 'release' agora suporta a geração opcional de uma nota de release simples.
@cli.command()
@log_command_execution
@click.argument('version')
@click.argument('message')
@click.option('--remote', default='origin', help='Nome do remote Git (padrão: origin).')
@click.option('--create-release', is_flag=True, help='Tenta criar uma release no GitHub (requer autenticação configurada).')
def release(version, message, remote, create_release):
    """
    Cria uma tag Git para a versão especificada e opcionalmente prepara uma release no GitHub.
    
    Exemplo: doxoade release v1.2.0 "Lançamento da versão 1.2.0" --create-release
    """
    click.echo(Fore.CYAN + f"--- [RELEASE] Criando tag Git para versão {version} ---")

    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        if not _run_git_command(['tag', version, '-a', '-m', message]):
            click.echo(Fore.RED + "[ERRO] Falha ao criar a tag Git.")
            return
        
        click.echo(Fore.GREEN + f"[OK] Tag Git '{version}' criada com sucesso.")
        
        # Tentativa de push da tag (se o remote estiver configurado)
        if _run_git_command(['push', remote, version]):
            click.echo(Fore.GREEN + f"[OK] Tag '{version}' enviada para o remote '{remote}'.")
        else:
            click.echo(Fore.YELLOW + f"[AVISO] Falha ao enviar a tag '{version}' para o remote '{remote}'. Certifique-se de que o remote está configurado e você tem permissões.")
    
        if create_release:
            # Lógica para criação de release no GitHub (requer mais interatividade ou API)
            # Por enquanto, apenas informa ao usuário
            click.echo(Fore.YELLOW + "\n[INFO] A criação automática de release no GitHub requer autenticação.")
            click.echo(Fore.YELLOW + "Você pode criar manualmente a release em:")
            click.echo(f"   https://github.com/{_get_github_repo_info()}/releases/new?tag={version}&title={version}")
            click.echo(Fore.YELLOW + f"Mensagem sugerida para a release: '{message}'")
    finally:
        _log_execution('sync', ".", results, {'remote': remote})

#atualizado em 2025/09/23-Versão 5.4. Corrigido bug crítico onde 'sync' não executava 'git push'. Tem como função sincronizar o branch local com o remoto (puxar e empurrar). Melhoria: Adicionado '--no-edit' ao pull para evitar prompts de merge em scripts.
@cli.command()
@log_command_execution
@click.option('--remote', default='origin', help='Nome do remote Git (padrão: origin).')
def sync(remote):
    """Sincroniza o branch local atual com o branch remoto (git pull && git push)."""
    click.echo(Fore.CYAN + f"--- [SYNC] Sincronizando branch com o remote '{remote}' ---")

    current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
    if not current_branch:
        click.echo(Fore.RED + "[ERRO] Não foi possível determinar o branch atual.")
        sys.exit(1)
    
    click.echo(f"   > Branch atual: '{current_branch}'")
    
    # --- PASSO 1: PUXAR ALTERAÇÕES DO REMOTE ---
    click.echo(Fore.YELLOW + "\nPasso 1: Puxando as últimas alterações do remote (git pull)...")
    if not _run_git_command(['pull', '--no-edit', remote, current_branch]):
        click.echo(Fore.RED + "[ERRO] Falha ao realizar o 'git pull'. Verifique conflitos de merge ou problemas de permissão.")
        sys.exit(1)
    click.echo(Fore.GREEN + "[OK] Repositório local atualizado.")

    # --- PASSO 2: EMPURRAR ALTERAÇÕES LOCAIS ---
    click.echo(Fore.YELLOW + "\nPasso 2: Enviando alterações locais para o remote (git push)...")
    #status_output = _run_git_command(['status', '--porcelain'], capture_output=True)
    if "ahead" not in _run_git_command(['status', '-sb'], capture_output=True):
        click.echo(Fore.GREEN + "[OK] Nenhum commit local para enviar. O branch já está sincronizado.")
    elif not _run_git_command(['push', remote, current_branch]):
        click.echo(Fore.RED + "[ERRO] Falha ao realizar o 'git push'. Verifique sua conexão ou permissões.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "[OK] Commits locais enviados com sucesso.")

    click.echo(Fore.GREEN + Style.BRIGHT + "\n[SYNC] Sincronização concluída com sucesso!")

#atualizado em 2025/09/28-Versão 14.0. Refatorado para usar o novo ExecutionLogger.
@cli.command('git-clean')
@click.pass_context
def git_clean(ctx):
    """Força a remoção de arquivos já rastreados que correspondem ao .gitignore."""
    # O path e os argumentos são extraídos do contexto do click
    path = '.'
    arguments = ctx.params

    with ExecutionLogger('git-clean', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [GIT-CLEAN] Procurando por arquivos rastreados indevidamente ---")
        
        gitignore_path = '.gitignore'
        if not os.path.exists(gitignore_path):
            msg = "Arquivo .gitignore não encontrado no diretório atual."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            return # Encerramos a função, mas o log será escrito pelo __exit__

        try:
            with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
                ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except Exception as e:
            msg = f"Não foi possível ler o arquivo .gitignore: {e}"
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}"); return
        
        tracked_files_str = _run_git_command(['ls-files'], capture_output=True)
        if tracked_files_str is None:
            sys.exit(1)
        tracked_files = tracked_files_str.splitlines()
    
        files_to_remove = []
        for pattern in ignore_patterns:
            if pattern.endswith('/'):
                pattern += '*'
            matches = fnmatch.filter(tracked_files, pattern)
            if matches:
                files_to_remove.extend(matches)
        
        if not files_to_remove:
            click.echo(Fore.GREEN + "[OK] Nenhum arquivo rastreado indevidamente encontrado. Seu repositório está limpo!")
            return
    
        click.echo(Fore.YELLOW + "\nOs seguintes arquivos estão sendo rastreados pelo Git, mas correspondem a padrões no seu .gitignore:")
        for f in files_to_remove:
            click.echo(f"  - {f}")
        
        if click.confirm(Fore.RED + "\nVocê tem certeza de que deseja parar de rastrear (untrack) TODOS estes arquivos?", abort=True):
            click.echo(Fore.CYAN + "Removendo arquivos do índice do Git...")
            success = True
            for f in files_to_remove:
                if not _run_git_command(['rm', '--cached', f]):
                    success = False
            
            if success:
                click.echo(Fore.GREEN + "\n[OK] Arquivos removidos do rastreamento com sucesso.")
                click.echo(Fore.YELLOW + "Suas alterações foram preparadas (staged).")
                click.echo(Fore.YELLOW + "Para finalizar, execute o seguinte comando:")
                click.echo(Fore.CYAN + '  doxoade save "Limpeza de arquivos ignorados"')
            else:
                click.echo(Fore.RED + "[ERRO] Ocorreu um erro ao remover um ou mais arquivos.")

#atualizado em 2025/09/23-Versão 5.3. Implementa o comando 'git-new' para a primeira publicação de um projeto. Tem como função automatizar o boilerplate de adicionar remote, commitar e fazer o primeiro push. Melhoria: Adicionada verificação se o remote 'origin' já existe.
@cli.command('git-new')
@log_command_execution
@click.argument('message')
@click.argument('remote_url')
def git_new(message, remote_url):
    """
    Automatiza a publicação de um novo projeto local em um repositório remoto VAZIO.

    Este comando executa a sequência completa de boilerplate do Git:
    1. git remote add origin <URL>
    2. git add .
    3. git commit -m "MENSAGEM"
    4. git push -u origin main

    Exemplo:
      doxoade git-new "Commit inicial do projeto" https://github.com/usuario/repo.git
    """
    click.echo(Fore.CYAN + "--- [GIT-NEW] Publicando novo projeto no GitHub ---")
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        # Passo 1: Adicionar o repositório remoto
        click.echo(Fore.YELLOW + f"Passo 1: Adicionando remote 'origin' -> {remote_url}")
        if not _run_git_command(['remote', 'add', 'origin', remote_url]):
            # A falha mais comum é o remote já existir. Damos um feedback útil.
            click.echo(Fore.RED + "[ERRO] Falha ao adicionar o remote. Motivo comum: o remote 'origin' já existe.")
            click.echo(Fore.YELLOW + "Se o projeto já tem um remote, use 'doxoade save' e 'git push' para atualizá-lo.")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Remote adicionado com sucesso.")
    
        # Passo 2: Adicionar todos os arquivos ao staging
        click.echo(Fore.YELLOW + "\nPasso 2: Adicionando todos os arquivos ao Git (git add .)...")
        if not _run_git_command(['add', '.']):
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados para o commit.")
    
        # Passo 3: Fazer o commit inicial
        click.echo(Fore.YELLOW + f"\nPasso 3: Criando o primeiro commit com a mensagem: '{message}'...")
        if not _run_git_command(['commit', '-m', message]):
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Commit inicial criado.")
    
        # Passo 4: Fazer o push para o repositório remoto
        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
        if not current_branch:
            click.echo(Fore.RED + "[ERRO] Não foi possível determinar o branch atual para o push.")
            sys.exit(1)
        
        click.echo(Fore.YELLOW + f"\nPasso 4: Enviando o branch '{current_branch}' para o remote 'origin' (git push)...")
        if not _run_git_command(['push', '--set-upstream', 'origin', current_branch]):
            click.echo(Fore.RED + "[ERRO] Falha ao enviar para o repositório remoto.")
            click.echo(Fore.YELLOW + "Causas comuns: a URL do repositório está incorreta, você não tem permissão, ou o repositório remoto NÃO ESTÁ VAZIO.")
            sys.exit(1)
        
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[GIT-NEW] Projeto publicado com sucesso!")
        click.echo(f"Você pode ver seu repositório em: {remote_url}")
    finally:
        _log_execution('git_new', ".", results, {})

#atualizado em 2025/09/25-Versão 9.2. Corrigida a lógica do '--force' no comando 'save' para ignorar o erro de ambiente mesmo na presença de outros erros.
@cli.command()
@log_command_execution
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo que o 'check' encontre avisos ou apenas o erro de ambiente.")
def save(message, force):
    """Executa um 'commit seguro', protegendo seu repositório de código com erros."""
    click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")
    click.echo(Fore.YELLOW + "\nPasso 1: Executando 'doxoade check' para garantir a qualidade do código...")

    config = _load_config()
    ignore_list = config.get('ignore', [])
    
    check_command = [sys.executable, '-m', 'doxoade.doxoade', 'check', '.']
    for folder in ignore_list:
        check_command.extend(['--ignore', folder])

    check_result = subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace')

    output = check_result.stdout
    return_code = check_result.returncode
    has_warnings = "Aviso(s)" in output and "0 Aviso(s)" not in output
    is_env_error_present = "Ambiente Inconsistente" in output
    
    # Contamos quantos erros *reais* existem, além do erro de ambiente.
    num_errors = int(re.search(r'(\d+) Erro\(s\)', output).group(1)) if re.search(r'(\d+) Erro\(s\)', output) else 0
    num_non_env_errors = num_errors - 1 if is_env_error_present else num_errors

    # --- NOVA LÓGICA DE DECISÃO ---
    if return_code != 0:
        if force and num_non_env_errors == 0:
            click.echo(Fore.YELLOW + "\n[AVISO] Erro de ambiente ignorado devido ao uso da flag --force.")
        else:
            click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros críticos. O salvamento foi abortado.")
            safe_output = output.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
            print(safe_output)
            sys.exit(1)
    
    if has_warnings and not force:
        if not click.confirm(Fore.YELLOW + "\n[AVISO] 'doxoade check' encontrou avisos. Deseja continuar com o salvamento mesmo assim?"):
            click.echo("Salvamento abortado pelo usuário."); sys.exit(0)
    
    click.echo(Fore.GREEN + "[OK] Verificação de qualidade concluída.")
    
    click.echo(Fore.YELLOW + "\nPasso 2: Verificando se há alterações para salvar...")
    status_output = _run_git_command(['status', '--porcelain'], capture_output=True)
    if status_output is None: sys.exit(1)
        
    if not status_output:
        click.echo(Fore.GREEN + "[OK] Nenhuma alteração nova para salvar. A árvore de trabalho está limpa."); return

    click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
    if not _run_git_command(['commit', '-a', '-m', message]):
        click.echo(Fore.YELLOW + "Tentativa inicial de commit falhou (pode haver arquivos novos). Tentando com 'git add .'...")
        if not _run_git_command(['add', '.']): sys.exit(1)
        if not _run_git_command(['commit', '-m', message]): sys.exit(1)
        
    click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso no repositório!")

#atualizado em 2025/09/26-Versão 10.0. Comando 'init' agora suporta publicação automática com a opção '--remote'. Tem como função criar um novo projeto e, opcionalmente, publicá-lo no GitHub em um único passo.
@cli.command()
@log_command_execution
@click.argument('project_name', required=False)
@click.option('--remote', help="URL do repositório Git remoto para publicação automática.")
def init(project_name, remote):
    """Cria a estrutura de um novo projeto e, opcionalmente, o publica no GitHub."""
    click.echo(Fore.CYAN + "--- [INIT] Assistente de Criação de Novo Projeto ---")
    if not project_name:
        project_name = click.prompt("Qual é o nome do seu novo projeto?")
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        click.echo(Fore.RED + "[ERRO] O nome do projeto deve conter apenas letras, números, hífens e underscores."); return
    
    project_path = os.path.abspath(project_name)
    if os.path.exists(project_path):
        click.echo(Fore.RED + f"[ERRO] O diretório '{project_path}' já existe."); return
        
    original_dir = os.getcwd()
    
    try:
        # --- LÓGICA DE CRIAÇÃO LOCAL (EXISTENTE) ---
        click.echo(f"   > Criando a estrutura do projeto em: {project_path}")
        os.makedirs(project_path)
        
        click.echo("   > Criando ambiente virtual 'venv'...")
        subprocess.run([sys.executable, "-m", "venv", os.path.join(project_path, "venv")], check=True, capture_output=True)

        click.echo("   > Criando arquivo .gitignore...")
        gitignore_content = ("venv/\n\n__pycache__/\n*.py[cod]\n\nbuild/\ndist/\n*.egg-info/\n\n.vscode/\n.idea/\n\n.env\n")
        with open(os.path.join(project_path, ".gitignore"), "w", encoding="utf-8") as f: f.write(gitignore_content)
        
        click.echo("   > Criando arquivo requirements.txt...")
        with open(os.path.join(project_path, "requirements.txt"), "w", encoding="utf-8") as f: f.write("# Adicione suas dependências aqui\n")
        
        click.echo("   > Criando arquivo main.py inicial...")
        main_py_content = (f"def main():\n    print(\"Bem-vindo ao {project_name}!\")\n\nif __name__ == '__main__':\n    main()\n")
        with open(os.path.join(project_path, "main.py"), "w", encoding="utf-8") as f: f.write(main_py_content)

        click.echo("   > Inicializando repositório Git...")
        os.chdir(project_path)
        if not _run_git_command(['init', '-b', 'main']):
            return

        click.echo(Fore.GREEN + "\n[OK] Estrutura local do projeto criada com sucesso!")

        # --- NOVA LÓGICA DE PUBLICAÇÃO AUTOMÁTICA ---
        if remote:
            click.echo(Fore.CYAN + "\n--- Publicando projeto no repositório remoto ---")
            
            click.echo(f"   > Adicionando remote 'origin' -> {remote}")
            if not _run_git_command(['remote', 'add', 'origin', remote]): return
            
            click.echo("   > Adicionando todos os arquivos ao Git (git add .)...")
            if not _run_git_command(['add', '.']): return

            commit_message = f"Commit inicial: Estrutura do projeto {project_name}"
            click.echo(f"   > Criando commit inicial com a mensagem: '{commit_message}'...")
            if not _run_git_command(['commit', '-m', commit_message]): return

            click.echo("   > Enviando para o branch 'main' no remote 'origin' (git push)...")
            if not _run_git_command(['push', '--set-upstream', 'origin', 'main']):
                click.echo(Fore.RED + "[ERRO] Falha ao enviar. Verifique a URL, suas permissões e se o repositório remoto está VAZIO.")
                return

            click.echo(Fore.GREEN + "\n[OK] Projeto publicado com sucesso!")
            click.echo(f"   > Veja seu repositório em: {remote}")
        
        else:
            click.echo(Fore.YELLOW + "\nLembrete: Este é um projeto local. Para publicá-lo mais tarde, use 'doxoade git-new'.")

    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado: {e}")
    finally:
        os.chdir(original_dir)

#atualizado em 2025/09/28-Versão 13.3. Comando 'mk' agora suporta sintaxe de expansão de chaves para criar múltiplos arquivos em um diretório (ex: "src/{a.py, b.py}").
@cli.command('mk')
@log_command_execution
@click.argument('items', nargs=-1, required=True)
@click.option('--path', '-p', 'base_path', default='.', type=click.Path(exists=True, file_okay=False, resolve_path=True), help="Diretório base onde a estrutura será criada.")
def mk(base_path, items):
    """
    Cria arquivos e pastas rapidamente. Pastas devem terminar com '/'.
    
    Suporta expansão de chaves para múltiplos arquivos:
    
    Exemplos:
      doxoade mk src/ tests/ main.py
      doxoade mk "src/app/{models.py, views.py, controllers.py}"
    """
    click.echo(Fore.CYAN + f"--- [MK] Criando estrutura em '{base_path}' ---")
    
    processed_items = []
    # --- NOVA LÓGICA DE EXPANSÃO ---
    # Primeiro, processamos os itens para expandir a sintaxe de chaves
    for item in items:
        match = re.match(r'^(.*)\{(.*)\}(.*)$', item)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            # Quebra o conteúdo das chaves pela vírgula
            filenames = [name.strip() for name in content.split(',')]
            for filename in filenames:
                processed_items.append(f"{prefix}{filename}{suffix}")
        else:
            processed_items.append(item)

    created_count = 0
    for item in processed_items:
        normalized_item = os.path.normpath(item)
        full_path = os.path.join(base_path, normalized_item)
        
        try:
            if item.endswith(('/', '\\')):
                os.makedirs(full_path, exist_ok=True)
                click.echo(Fore.GREEN + f"[CRIADO] Diretório: {full_path}")
                created_count += 1
            else:
                parent_dir = os.path.dirname(full_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                
                if not os.path.exists(full_path):
                    Path(full_path).touch()
                    click.echo(Fore.GREEN + f"[CRIADO] Arquivo:   {full_path}")
                    created_count += 1
                else:
                    click.echo(Fore.YELLOW + f"[EXISTE] Arquivo:   {full_path}")
        except OSError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao criar '{full_path}': {e}")
            continue
            
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Concluído ---")
    click.echo(f"{created_count} novo(s) item(ns) criado(s).")

#atualizado em 2025/09/26-Versão 11.0. Novo comando 'create-pipeline' para gerar arquivos de automação de forma segura, resolvendo todos os problemas de parsing.
@cli.command('create-pipeline')
@click.argument('filename')
@click.argument('commands', nargs=-1, required=True)
def create_pipeline(filename, commands):
    """
    Cria um arquivo de pipeline (.dox) com uma sequência de comandos.

    Cada comando deve ser passado como um argumento separado e entre aspas.
    Exemplo:
      doxoade create-pipeline deploy.dox "doxoade health" "doxoade save 'Deploy final' --force"
    """
    click.echo(Fore.CYAN + f"--- [CREATE-PIPELINE] Criando arquivo de pipeline: {filename} ---")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Pipeline gerado pelo doxoade em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for command in commands:
                f.write(f"{command}\n")
        
        click.echo(Fore.GREEN + f"[OK] Pipeline '{filename}' criado com sucesso com {len(commands)} passo(s).")
        click.echo(Fore.YELLOW + f"Agora você pode executá-lo com: doxoade auto --file {filename}")
    except IOError as e:
        click.echo(Fore.RED + f"[ERRO] Não foi possível escrever no arquivo '{filename}': {e}")
        sys.exit(1)

#atualizado em 2025/09/26-Versão 12.1 (Final Definitiva). 'auto' agora usa um pipeline de arquivo temporário E o parser shlex, resolvendo de uma vez por todas todos os bugs de parsing de aspas em todos os ambientes.
@cli.command()
@log_command_execution
@click.argument('commands', nargs=-1, required=True)
def auto(commands):
    """
    Executa uma sequência de comandos como um pipeline robusto.

    Envolva cada comando, especialmente os que contêm espaços ou aspas,
    em suas próprias aspas duplas. Use aspas simples ou duplas para mensagens internas.
    Exemplo:
      doxoade auto "doxoade health" "doxoade save 'Deploy final' --force"
    """
    if not commands:
        click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

    total_commands = len(commands)
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {total_commands} passo(s) ---")
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=True, suffix='.dox', encoding='utf-8') as temp_pipeline:
        for command in commands:
            temp_pipeline.write(f"{command}\n")
        temp_pipeline.flush()
        temp_pipeline.seek(0)
        commands_to_run = [line.strip() for line in temp_pipeline if line.strip() and not line.strip().startswith('#')]

    results = []
    try:
        for i, command_str in enumerate(commands_to_run, 1):
            click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{total_commands}: {command_str} ---")
            step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
            try:
                # --- LÓGICA FINAL, DEFINITIVA E CORRETA ---
                # Usamos shlex para quebrar o comando em uma lista, respeitando as aspas.
                args = shlex.split(command_str)
                
                # Se o comando é 'doxoade', nós o chamamos como um módulo para máxima robustez.
                if args[0] == 'doxoade':
                    final_command = [sys.executable, '-m', 'doxoade.doxoade'] + args[1:]
                    use_shell = False
                else: # Para comandos externos (ex: git), passamos a lista diretamente.
                    final_command = args
                    use_shell = True # Shell pode ser necessário para encontrar comandos como 'git'

                process_result = subprocess.run(final_command, shell=use_shell, capture_output=True, text=True, encoding='utf-8', errors='replace')
                
                if process_result.stdout: print(process_result.stdout)
                if process_result.stderr: print(Fore.RED + process_result.stderr)
                if process_result.returncode != 0:
                    step_result["status"] = "falha"; step_result["returncode"] = process_result.returncode
            except Exception as e:
                step_result["status"] = "falha"; step_result["error"] = str(e)
            results.append(step_result)
    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n [AUTO] Pipeline cancelado pelo usuário.")
        sys.exit(1)
        
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- [AUTO] Sumário do Pipeline ---")
    final_success = True
    for i, result in enumerate(results, 1):
        if result["status"] == "sucesso":
            click.echo(Fore.GREEN + f"[OK] Passo {i}: Sucesso -> {result['command']}")
        else:
            final_success = False
            error_details = result.get('error', f"código de saída {result['returncode']}")
            click.echo(Fore.RED + f"[ERRO] Passo {i}: Falha ({error_details}) -> {result['command']}")
    click.echo("-" * 40)
    if final_success:
        click.echo(Fore.GREEN + Style.BRIGHT + "[AUTO] Pipeline concluído com sucesso!")
    else:
        click.echo(Fore.RED + Style.BRIGHT + "[ATENÇÃO] Pipeline executado, mas um ou mais passos falharam.")
        sys.exit(1)

@cli.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fix', is_flag=True, help="Tenta corrigir automaticamente os problemas encontrados.")
def check(path, ignore, format, fix):
    """Executa um diagnóstico completo de ambiente e código no projeto."""
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        if format == 'text': click.echo(Fore.YELLOW + f"[CHECK] Executando 'doxoade check' no diretório '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config['ignore'] + list(ignore)))
        results.update({'environment': [], 'dependencies': [], 'source_code': []})

        results['environment'] = _check_environment(path)
        results['dependencies'] = _check_dependencies(path)
        results['source_code'] = _check_source_code(path, final_ignore_list, fix_errors=fix, text_format=(format == 'text'))
        _update_summary_from_findings(results)
        _present_results(format, results)
    
    except Exception as e:
        safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        click.echo(Fore.RED + f"\n[ERRO FATAL] O 'check' falhou inesperadamente: {safe_error}", err=True)
        results['summary']['errors'] += 1
    finally:
        _log_execution(command_name='check', path=path, results=results, arguments={"ignore": list(ignore), "format": format, "fix": fix})
        if results['summary']['errors'] > 0:
            sys.exit(1)

@cli.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def webcheck(path, ignore, format):
    """Analisa arquivos .html, .css e .js em busca de problemas comuns."""
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        if format == 'text': click.echo(Fore.YELLOW + f"[WEB] Executando 'doxoade webcheck' no diretório '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config['ignore'] + list(ignore)))
        results.update({'web_assets': _check_web_assets(path, final_ignore_list)})
        _update_summary_from_findings(results)
        _present_results(format, results)
    except Exception as e:
        safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        click.echo(Fore.RED + f"\n[ERRO FATAL] O 'webcheck' falhou inesperadamente: {safe_error}", err=True)
        results['summary']['errors'] += 1
    finally:
        _log_execution(command_name='webcheck', path=path, results=results, arguments={"ignore": list(ignore), "format": format})
        if results['summary']['errors'] > 0:
            sys.exit(1)

@cli.command()
@click.argument('path', type=click.Path(exists=True, file_okay=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def guicheck(path, ignore, format):
    """Analisa arquivos .py em busca de problemas de GUI (Tkinter)."""
    results = {'summary': {'errors': 0, 'warnings': 0}}
    try:
        if format == 'text': click.echo(Fore.YELLOW + f"[GUI] Executando 'doxoade guicheck' no caminho '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config['ignore'] + list(ignore)))
        results.update({'gui': _check_gui_files(path, final_ignore_list)})
        _update_summary_from_findings(results)
        _present_results(format, results)
    except Exception as e:
        safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        click.echo(Fore.RED + f"\n[ERRO FATAL] O 'guicheck' falhou inesperadamente: {safe_error}", err=True)
        results['summary']['errors'] += 1
    finally:
        _log_execution(command_name='guicheck', path=path, results=results, arguments={"ignore": list(ignore), "format": format})
        if results['summary']['errors'] > 0:
            sys.exit(1)

#atualizado em 2025/09/20-V49. Arquitetura do 'run' refeita para suportar scripts interativos (input()), herdando os fluxos de I/O do terminal.
@cli.command(context_settings=dict(ignore_unknown_options=True))
@log_command_execution
@click.argument('script_and_args', nargs=-1, type=click.UNPROCESSED)
def run(script_and_args):
    """Executa um script Python, suportando interatividade (input) e GUIs."""

    if not script_and_args:
        click.echo(Fore.RED + "[ERRO] Erro: Nenhum script especificado para executar.", err=True); sys.exit(1)
    
    script_name = script_and_args[0]
    if not os.path.exists(script_name):
        click.echo(Fore.RED + f"[ERRO] Erro: Não foi possível encontrar o script '{script_name}'."); sys.exit(1)
        
    venv_path = 'venv'
    python_executable = os.path.join(venv_path, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(venv_path, 'bin', 'python')
    if not os.path.exists(python_executable):
        click.echo(Fore.RED + f"[ERRO] Erro: Ambiente virtual não encontrado em '{python_executable}'.", err=True); sys.exit(1)
        
    command_to_run = [python_executable, '-u'] + list(script_and_args)
    click.echo(Fore.CYAN + f"-> Executando '{' '.join(script_and_args)}' com o interpretador do venv...")
    click.echo(Fore.YELLOW + f"   (Caminho do Python: {python_executable})")
    click.echo("-" * 40)
    
    process = None
    return_code = 1
    
    try:
        # --- MUDANÇA ARQUITETURAL ---
        # Não especificamos stdout, stderr ou stdin.
        # Isso faz com que o processo filho herde o terminal do pai,
        # permitindo a entrada (input) e a saída (print) diretas.
        process = subprocess.Popen(command_to_run)
        
        # Como não estamos capturando a saída, simplesmente esperamos o processo terminar.
        # O Popen não é bloqueante, então o KeyboardInterrupt ainda funciona.
        process.wait()
        return_code = process.returncode

    except KeyboardInterrupt:
        click.echo("\n" + Fore.YELLOW + "[RUN] Interrupção detectada (CTRL+C). Encerrando o script filho...")
        if process: process.terminate()
        return_code = 130
    except Exception as e:
        safe_error = str(e).encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado ao executar o script: {safe_error}", err=True)
        if process: process.kill()
        sys.exit(1)
    finally:
        if process and process.poll() is None:
            process.kill()

    click.echo("-" * 40)
    
    # IMPORTANTE: Como não capturamos mais o stderr, o diagnóstico pós-execução se torna impossível.
    # Esta é uma troca consciente: ganhamos interatividade, mas perdemos a análise de traceback.
    if return_code != 0:
        click.echo(Fore.RED + f"[ERRO] O script '{script_name}' terminou com o código de erro {return_code}.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + f"[OK] Script '{script_name}' finalizado com sucesso.")

@cli.command()
@log_command_execution
@click.option('--force', '-f', is_flag=True, help="Força a limpeza sem pedir confirmação.")
def clean(force):
    """Remove arquivos de cache e build (__pycache__, build/, dist/, *.spec)."""

    TARGET_DIRS = ["__pycache__", "build", "dist", ".pytest_cache", ".tox"]
    TARGET_PATTERNS = [re.compile(r".*\.egg-info$"), re.compile(r".*\.spec$")]
    click.echo(Fore.CYAN + "-> [CLEAN] Procurando por artefatos de build e cache...")
    targets_to_delete = []
    for root, dirs, files in os.walk('.', topdown=True):
        # Correção: A lógica estava invertida. Agora removemos os diretórios 'venv'.
        dirs[:] = [d for d in dirs if 'venv' not in d and '.git' not in d]
        for name in list(dirs):
            if name in TARGET_DIRS or any(p.match(name) for p in TARGET_PATTERNS):
                targets_to_delete.append(os.path.join(root, name))
        for name in files:
            if any(p.match(name) for p in TARGET_PATTERNS):
                targets_to_delete.append(os.path.join(root, name))
    if not targets_to_delete:
        click.echo(Fore.GREEN + "[OK] O projeto já está limpo."); return
    click.echo(Fore.YELLOW + f"Encontrados {len(targets_to_delete)} itens para remover:")
    for target in targets_to_delete: click.echo(f"  - {target}")
    if force or click.confirm(f"\n{Fore.YELLOW}Remover permanentemente estes itens?"):
        deleted_count = 0
        click.echo(Fore.CYAN + "\n-> Iniciando a limpeza...")
        for target in targets_to_delete:
            try:
                if os.path.isdir(target): shutil.rmtree(target); click.echo(f"  {Fore.RED}Removido diretório: {target}")
                elif os.path.isfile(target): os.remove(target); click.echo(f"  {Fore.RED}Removido arquivo: {target}")
                deleted_count += 1
            except OSError as e: click.echo(Fore.RED + f"  Erro ao remover {target}: {e}", err=True)
        click.echo(Fore.GREEN + f"\n Limpeza concluída! {deleted_count} itens foram removidos.")
    else:
        click.echo(Fore.CYAN + "\nOperação cancelada.")
    
#atualizado em 2025/09/16-V26. Adicionada a flag '--snippets' para exibir o contexto de código nos logs.
@cli.command()
@log_command_execution
@click.option('-n', '--lines', default=1, help="Exibe as últimas N linhas do log.", type=int)
@click.option('-s', '--snippets', is_flag=True, help="Exibe os trechos de código para cada problema.")
def log(lines, snippets):
    """Exibe as últimas entradas do arquivo de log do doxoade."""
    log_file = Path.home() / '.doxoade' / 'doxoade.log'
    
    if not log_file.exists():
        click.echo(Fore.YELLOW + "Nenhum arquivo de log encontrado. Execute um comando de análise primeiro."); return

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        if not all_lines:
            click.echo(Fore.YELLOW + "O arquivo de log está vazio."); return
            
        last_n_lines = all_lines[-lines:]
        
        total_to_show = len(last_n_lines)
        for i, line in enumerate(last_n_lines):
            try:
                entry = json.loads(line)
                # Passa a flag 'snippets' para a função de exibição
                _display_log_entry(entry, index=i + 1, total=total_to_show, show_snippets=snippets)
            except json.JSONDecodeError:
                click.echo(Fore.RED + f"--- Erro ao ler a entrada #{i + 1} ---")
                click.echo(Fore.RED + "A linha no arquivo de log não é um JSON válido.")
                click.echo(Fore.YELLOW + f"Conteúdo da linha: {line.strip()}")
    except Exception as e:
        click.echo(Fore.RED + f"Ocorreu um erro ao ler o arquivo de log: {e}", err=True)

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------

# A função _get_github_repo_info() e _run_git_command() já existem no seu código.
# Certifique-se de que elas estejam corretamente implementadas e acessíveis.
# Se _get_github_repo_info() ainda não existe, ela precisaria ser implementada para extrair
# o nome do usuário e repositório do .git/config ou de comandos como 'git remote get-url origin'.

def _get_github_repo_info():
    """Extrai a informação do repositório GitHub (usuário/repo) do .git/config."""
    try:
        url = _run_git_command(['remote', 'get-url', 'origin'], capture_output=True)
        if url is None: return "unkown/unkown"
        
        # Tenta extrair de SSH URLs (git@github.com:usuario/repo.git)
        match_ssh = re.match(r'git@github\.com:([\w-]+)/([\w-]+)\.git', url)
        if match_ssh: return f"{match_ssh.group(1)}/{match_ssh.group(2)}"
        
        # Tenta extrair de HTTPS URLs (https://github.com/usuario/repo.git)
        match_https = re.match(r'https?://github\.com/([\w-]+)/([\w-]+)\.git', url)
        if match_https: return f"{match_https.group(1)}/{match_https.group(2)}"
        
    except Exception:
        pass
    return "unkown/unkown"

def _get_git_commit_hash(path):
    """Obtém o hash do commit Git atual (HEAD) de forma silenciosa."""
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        # Usamos silent_fail=True para evitar mensagens de erro em pastas não-Git.
        hash_output = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True)
        return hash_output if hash_output else "N/A"
    except Exception:
        return "N/A"
    finally:
        os.chdir(original_dir)

#atualizado em 2025/09/27-Versão 12.6 (Final). _run_git_command agora suporta 'silent_fail' para que a captura de hash do log não gere erros em diretórios não-Git.
def _run_git_command(args, capture_output=False, silent_fail=False):
    """Executa um comando Git e lida com erros comuns."""
    try:
        command = ['git'] + args
        result = subprocess.run(
            command, 
            capture_output=capture_output, 
            text=True, 
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout.strip() if capture_output else True
    except FileNotFoundError:
        if not silent_fail:
            click.echo(Fore.RED + "[ERRO GIT] O comando 'git' não foi encontrado. O Git está instalado e no PATH do sistema?")
        return None
    except subprocess.CalledProcessError as e:
        if not silent_fail:
            click.echo(Fore.RED + f"[ERRO GIT] O comando 'git {' '.join(args)}' falhou:")
            error_output = e.stderr or e.stdout or "Nenhuma saída de erro do Git foi capturada."
            click.echo(Fore.YELLOW + error_output)
        return None

#atualizado em 2025/09/16-V26. Aprimorada para exibir snippets de código com destaque na linha do erro.
def _display_log_entry(entry, index, total, show_snippets=False):
    """Formata e exibe uma única entrada de log de forma legível, com snippets opcionais."""
    try:
        ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
        ts_local = ts.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, KeyError):
        ts_local = entry.get('timestamp', 'N/A')

    header = f"--- Entrada de Log #{index}/{total} ({ts_local}) ---"
    click.echo(Fore.CYAN + Style.BRIGHT + header)
    
    click.echo(Fore.WHITE + f"Comando: {entry.get('command', 'N/A')}")
    click.echo(Fore.WHITE + f"Projeto: {entry.get('project_path', 'N/A')}")
    
    summary = entry.get('summary', {})
    errors = summary.get('errors', 0)
    warnings = summary.get('warnings', 0)
    
    summary_color = Fore.RED if errors > 0 else Fore.YELLOW if warnings > 0 else Fore.GREEN
    click.echo(summary_color + f"Resultado: {errors} Erro(s), {warnings} Aviso(s)")

    findings = entry.get('findings')
    if findings:
        click.echo(Fore.WHITE + "Detalhes dos Problemas Encontrados:")
        for finding in findings:
            f_type = finding.get('type', 'info').upper()
            f_color = Fore.RED if f_type == 'ERROR' else Fore.YELLOW
            f_msg = finding.get('message', 'N/A')
            f_file = finding.get('file', 'N/A')
            f_line = finding.get('line', '')
            click.echo(f_color + f"  - [{f_type}] {f_msg} (em {f_file}, linha {f_line})")

            # --- NOVA LÓGICA PARA EXIBIR SNIPPETS ---
            snippet = finding.get('snippet')
            if show_snippets and snippet:
                for line_num_str, code_line in snippet.items():
                    line_num = int(line_num_str)
                    # Compara o número da linha do snippet com a linha do finding
                    if line_num == f_line:
                        # Destaque para a linha do erro
                        click.echo(Fore.WHITE + Style.BRIGHT + f"    > {line_num:3}: {code_line}")
                    else:
                        # Contexto normal
                        click.echo(Fore.WHITE + f"      {line_num:3}: {code_line}")
    click.echo("")
    
#atualizado em 2025/09/16-V23. Nova função auxiliar para extrair trechos de código de arquivos, enriquecendo os logs.
def _get_code_snippet(file_path, line_number, context_lines=2):
    """
    Extrai um trecho de código de um arquivo, centrado em uma linha específica.
    Retorna um dicionário {numero_da_linha: 'código'} ou None se não for possível.
    """
    if not line_number or not isinstance(line_number, int) or line_number <= 0:
        return None
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        snippet = {}
        for i in range(start, end):
            # Armazena o número da linha (1-indexed) e o conteúdo da linha (sem o \n)
            snippet[i + 1] = lines[i].rstrip('\n')
            
        return snippet
    except (IOError, IndexError):
        # Retorna None se o arquivo não puder ser lido ou a linha não existir
        return None

#atualizado em 2025/09/27-Versão 12.7. Logging aprimorado para registrar todas as execuções e falhas internas, não apenas análises.
def _log_execution(command_name, path, results, arguments):
    """(Função Auxiliar) Escreve o dicionário de log final no arquivo."""
    try:
        # ... (a lógica interna de encontrar o arquivo e escrever o JSON permanece a mesma) ...
        log_dir = Path.home() / '.doxoade'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'doxoade.log'
        
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        git_hash = _get_git_commit_hash(path)

        log_data = {
            "timestamp": timestamp,
            "command": command_name,
            "project_path": os.path.abspath(path),
            "git_hash": git_hash,
            "arguments": arguments,
            "summary": results.get('summary', {}),
            "status": "completed",
            "findings": results.get('findings', [])
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_data) + '\n')
    except Exception:
        click.echo(Fore.RED + "\n[AVISO DE LOG] Não foi possível escrever no arquivo de log detalhado.", err=True)

def _check_environment(path):
    """Verifica o ambiente e retorna uma lista de problemas."""
    expected = os.path.abspath(os.path.join(path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python.exe' if os.name == 'nt' else 'python'))
    current = os.path.abspath(sys.executable)
    if current.lower() != expected.lower():
        return [{'type': 'error', 'message': 'Ambiente Inconsistente!', 'details': f'Terminal usa: {current}\n   > Projeto espera: {expected}', 'ref': 'OTRAN-Bug#2'}]
    return []

#atualizado em 2025/09/16-V23. Integração com _get_code_snippet para adicionar contexto de código aos findings.
def _check_dependencies(path):
    """Verifica requirements.txt e retorna uma lista de problemas com snippets."""
    findings = []
    req_file = os.path.join(path, 'requirements.txt')
    if not os.path.exists(req_file):
        return [{'type': 'warning', 'message': "Arquivo 'requirements.txt' não encontrado."}]
    CRITICAL_PACKAGES = ['numpy', 'opencv-python', 'Pillow']
    with open(req_file, 'r', encoding='utf-8') as f:
        # Usamos readlines() para ter acesso às linhas para o snippet
        lines = f.readlines()

    for i, line_content in enumerate(lines):
        line_num = i + 1
        line = line_content.strip()
        if line and not line.startswith('#'):
            for pkg in CRITICAL_PACKAGES:
                if line.lower().startswith(pkg) and not any(c in line for c in '==<>~'):
                    finding = {
                        'type': 'warning', 
                        'message': f"Pacote crítico '{pkg}' não tem versão fixada.", 
                        'details': "Considere fixar a versão (ex: 'numpy<2.0').", 
                        'ref': 'OTM-Bug#2', 
                        'file': req_file, 
                        'line': line_num
                    }
                    # Adiciona o snippet da linha específica
                    finding['snippet'] = {line_num: line}
                    findings.append(finding)
    return findings
    
#atualizado em 2025/09/29-Versão 15.1. Corrigido bug crítico onde a pasta 'venv' não era ignorada, causando uma avalanche de erros irrelevantes de bibliotecas de terceiros.
def _check_source_code(path, ignore_list=None, fix_errors=False, text_format=True):
    """Analisa arquivos .py e retorna uma lista de problemas."""
    findings = []
    
    # --- LÓGICA DE IGNORE CORRIGIDA E SIMPLIFICADA ---
    # Nós garantimos que 'venv' e outras pastas padrão estejam sempre na lista de ignorados.
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []

    for root, dirs, files in os.walk(path, topdown=True):
        # A forma correta e robusta de ignorar diretórios é modificar a lista 'dirs' in-place.
        # Isso impede que o 'os.walk' sequer entre nessas pastas.
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))

    unsafe_path_regex = re.compile(r'[^rR]"[a-zA-Z]:\\[^"]*"')

    for file_path in files_to_check:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            original_lines = content.splitlines()
        
        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        pyflakes_output = output_stream.getvalue().strip()
        
        if pyflakes_output:
            lines_to_remove = set()
            for line_error in pyflakes_output.splitlines():
                try:
                    parts = line_error.split(':', 2)
                    line_num = int(parts[1])
                    message_text = parts[2].strip()
                except (IndexError, ValueError):
                    line_num, message_text = 'N/A', line_error

                if "' imported but unused" in message_text and fix_errors:
                    lines_to_remove.add(line_num)
                else:
                    finding = {'type': 'error', 'message': message_text, 'ref': 'Pyflakes', 'file': file_path, 'line': line_num}
                    finding['snippet'] = _get_code_snippet(file_path, line_num)
                    findings.append(finding)
            
            if lines_to_remove:
                new_lines = [line for i, line in enumerate(original_lines) if (i + 1) not in lines_to_remove]
                with open(file_path, 'w', encoding='utf-8') as f: f.write("\n".join(new_lines))
                if text_format: click.echo(Fore.GREEN + f"   [FIXED] Em '{file_path}': Removidas {len(lines_to_remove)} importações não utilizadas.")
        
        if unsafe_path_regex.search(content):
            findings.append({'type': 'warning', 'message': 'Possível caminho de arquivo inseguro (use C:/ ou r"C:\\")', 'ref': 'ORI-Bug#2', 'file': file_path})
            
    return findings
    
def _check_web_assets(path, ignore_list=None):
    """Analisa arquivos web e retorna uma lista de problemas."""
    findings = []
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith(('.html', '.htm', '.css', '.js')):
                files_to_check.append(os.path.join(root, file))
    
    for file_path in files_to_check:
        if file_path.endswith(('.html', '.htm')): findings.extend(_analyze_html_file(file_path))
        elif file_path.endswith('.css'): findings.extend(_analyze_css_file(file_path))
        elif file_path.endswith('.js'): findings.extend(_analyze_js_file(file_path))
    return findings

#atualizado em 2025/09/23-Versão 5.1. Aprimorada a análise de layout para capturar e reportar os números de linha relevantes para os erros, melhorando a precisão do diagnóstico.
def _analyze_tkinter_layout(tree, file_path):
    """
    Analisa uma AST de um arquivo Python em busca de erros de design de layout Tkinter
    usando uma abordagem de múltiplas passagens e reportando números de linha.
    """
    findings = []
    
    # --- PRIMEIRA PASSAGEM: Construir o mapa de hierarquia (quem é pai de quem) ---
    widget_parent_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if node.value.args:
                parent_node = node.value.args[0]
                parent_name = None
                # Tenta extrair o nome do pai (ex: self.main_frame -> 'main_frame')
                if isinstance(parent_node, ast.Name): parent_name = parent_node.id
                elif isinstance(parent_node, ast.Attribute): parent_name = parent_node.attr
                
                # Tenta extrair o nome do widget filho (ex: self.my_button -> 'my_button')
                widget_name = None
                if hasattr(node.targets[0], 'id'): widget_name = node.targets[0].id
                elif hasattr(node.targets[0], 'attr'): widget_name = node.targets[0].attr

                if parent_name and widget_name:
                    widget_parent_map[widget_name] = parent_name

    # --- SEGUNDA PASSAGEM: Coletar dados de layout e configuração de grid ---
    # Estrutura aprimorada para guardar também o número da linha
    parent_layouts = {}  # {'parent_name': {'pack': [10, 15], 'grid': [12]}}
    grid_configs = {}    # {'parent_name': {'rows_weighted': {0, 1}, 'cols_weighted': {0}}}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            widget_name = None
            if isinstance(node.func.value, ast.Name): widget_name = node.func.value.id
            elif isinstance(node.func.value, ast.Attribute): widget_name = node.func.value.attr
                
            parent_name = widget_parent_map.get(widget_name)

            if node.func.attr in ['pack', 'grid']:
                layout_manager = node.func.attr
                if parent_name:
                    # Inicializa a estrutura se for o primeiro encontro
                    parent_layouts.setdefault(parent_name, {})
                    # Adiciona o número da linha à lista daquele gerenciador
                    parent_layouts[parent_name].setdefault(layout_manager, []).append(node.lineno)

            if node.func.attr in ['rowconfigure', 'columnconfigure'] and parent_name:
                has_weight = any(kw.arg == 'weight' and isinstance(kw.value, ast.Constant) and kw.value.value > 0 for kw in node.keywords)
                if has_weight:
                    config_type = 'rows_weighted' if node.func.attr == 'rowconfigure' else 'cols_weighted'
                    grid_configs.setdefault(parent_name, {'rows_weighted': set(), 'cols_weighted': set()})
                    if node.args and isinstance(node.args[0], ast.Constant):
                        index = node.args[0].value
                        grid_configs[parent_name][config_type].add(index)

    # --- ANÁLISE FINAL: Usar os dados coletados para encontrar problemas ---

    for parent, layouts in parent_layouts.items():
        # 1. Encontra pais com múltiplos gerenciadores de layout
        if len(layouts) > 1:
            # Concatena todas as linhas de todos os layouts para reportar
            all_lines = []
            for manager_lines in layouts.values():
                all_lines.extend(manager_lines)
            
            # Pega a primeira linha como a principal para o relatório
            line_report = min(all_lines) if all_lines else None
            
            findings.append({
                'type': 'error',
                'message': f"Uso misto de gerenciadores de layout ({', '.join(layouts.keys())}) no widget pai '{parent}'.",
                'details': f"As chamadas conflitantes foram encontradas nas linhas: {sorted(all_lines)}.",
                'ref': 'OADE-15',
                'file': file_path,
                'line': line_report 
            })

        # 2. Encontra pais que usam .grid mas não configuram o peso
        if 'grid' in layouts:
            if parent not in grid_configs or not (grid_configs[parent]['rows_weighted'] or grid_configs[parent]['cols_weighted']):
                # Reporta a linha da primeira chamada .grid() encontrada para este pai
                line_report = min(layouts['grid']) if layouts['grid'] else None
                findings.append({
                    'type': 'warning',
                    'message': f"O widget pai '{parent}' usa o layout .grid() mas não parece configurar o 'weight'.",
                    'details': "Sem 'weight' > 0 em .rowconfigure()/.columnconfigure(), o layout não será responsivo.",
                    'ref': 'OADE-15',
                    'file': file_path,
                    'line': line_report
                })
                
    return findings


def _check_gui_files(path, ignore_list=None):
    """Analisa arquivos Python de GUI e retorna uma lista de problemas."""
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'): files_to_check.append(os.path.join(root, file))
    elif path.endswith('.py'):
        files_to_check.append(path)
    
    findings = []
    for file_path in files_to_check:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        try:
            tree = ast.parse(content)
            # Executa ambas as análises e consolida os resultados
            findings.extend(_check_gui_events(tree, file_path))
            findings.extend(_analyze_tkinter_layout(tree, file_path))
        except SyntaxError as e:
            findings.append({'type': 'error', 'message': f"Erro de sintaxe Python impede análise: {e}", 'file': file_path, 'line': e.lineno})
    return findings


# -----------------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE ESPECÍFICAS (COLETA DE DADOS)
# -----------------------------------------------------------------------------

def _analyze_html_file(file_path):
    findings = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
    soup = BeautifulSoup(content, 'lxml')
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        if any(p in href for p in ['{{', '{%']) or href.startswith(('http', '#', 'mailto:', 'javascript:')): continue
        target = os.path.normpath(os.path.join(os.path.dirname(file_path), href))
        if not os.path.exists(target):
            findings.append({'type': 'error', 'message': f"Link quebrado para '{href}'", 'file': file_path})
    for tag in soup.find_all('img', alt=None):
        findings.append({'type': 'warning', 'message': f"Imagem sem atributo 'alt' (src: {tag.get('src', 'N/A')[:50]}...)", 'file': file_path})
    return findings

def _analyze_css_file(file_path):
    findings = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
    if content.lower().count('!important') > 3:
        findings.append({'type': 'warning', 'message': "Uso excessivo de '!important'", 'details': "Pode indicar problemas de especificidade.", 'file': file_path})
    if re.search(r'^\s*#\w|[\{,]\s*#\w', content):
        findings.append({'type': 'warning', 'message': "Seletor de ID ('#') encontrado.", 'details': "Pode criar regras muito específicas e difíceis de manter.", 'file': file_path})
    for match in re.finditer(r'url\(([^)]+)\)', content):
        url_path = match.group(1).strip(' \'"')
        if url_path.startswith(('data:', 'http', '//', '#')): continue
        target = os.path.normpath(os.path.join(os.path.dirname(file_path), url_path))
        if not os.path.exists(target):
            findings.append({'type': 'error', 'message': f"Link 'url()' quebrado para '{url_path}'", 'file': file_path})
    return findings

def _analyze_js_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
    try:
        esprima.parseScript(content)
        return []
    except esprima.Error as e:
        return [{'type': 'error', 'message': f"Erro de sintaxe JS: {e.message}", 'file': file_path, 'line': e.lineNumber}]

def _check_gui_events(tree, file_path):
    findings = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
    try: tree = ast.parse(content)
    except SyntaxError as e:
        return [{'type': 'error', 'message': f"Erro de sintaxe Python impede análise: {e}", 'file': file_path, 'line': e.lineno}]
    
    widget_creations = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and hasattr(node.value.func, 'attr') and 'Button' in node.value.func.attr:
            widget_name = node.targets[0].id if hasattr(node.targets[0], 'id') else node.targets[0].attr if hasattr(node.targets[0], 'attr') else None
            if widget_name:
                has_command = any(kw.arg == 'command' for kw in node.value.keywords)
                widget_creations[widget_name] = {'has_command': has_command, 'line': node.lineno}
    
    for name, data in widget_creations.items():
        if not data['has_command']:
            findings.append({'type': 'warning', 'message': f"Possível widget de botão '{name}' sem ação 'command'.", 'details': "Verifique se um evento .bind() foi associado a ele, ou se a ação está faltando.", 'file': file_path, 'line': data['line']})
    return findings

# -----------------------------------------------------------------------------
# FUNÇÕES DE APRESENTAÇÃO E DIAGNÓSTICO
# -----------------------------------------------------------------------------

def _update_summary_from_findings(results):
    """Atualiza o sumário de erros/avisos com base nos findings coletados."""
    for category in results:
        if category == 'summary': continue
        for finding in results[category]:
            if finding['type'] == 'warning': results['summary']['warnings'] += 1
            elif finding['type'] == 'error': results['summary']['errors'] += 1

def _present_results(format, results):
    """Apresenta os resultados no formato escolhido (JSON ou texto)."""
    if format == 'json':
        print(json.dumps(results, indent=4)); return

    category_titles = {
        'environment': '[AMBIENTE] ANÁLISE DE AMBIENTE',
        'dependencies': '[DEP] ANÁLISE DE DEPENDÊNCIAS',
        'source_code': '[LINT] ANÁLISE DE CÓDIGO',
        'web_assets': '[WEB] ANÁLISE DE ATIVOS WEB (HTML/CSS/JS)',
        'gui': '[GUI] ANÁLISE DE GUI (TKINTER)'
    }

    for category, findings in results.items():
        if category == 'summary': continue
        click.echo(Style.BRIGHT + f"\n--- {category_titles.get(category, category.upper())} ---")
        if not findings:
            click.echo(Fore.GREEN + "[OK] Nenhum problema encontrado nesta categoria.")
        else:
            for finding in findings:
                color = Fore.RED if finding['type'] == 'error' else Fore.YELLOW
                tag = '[ERRO]' if finding['type'] == 'error' else '[AVISO]'
                ref = f" [Ref: {finding.get('ref', 'N/A')}]" if finding.get('ref') else ""
                click.echo(color + f"{tag} {finding['message']}{ref}")
                if 'file' in finding:
                    location = f"   > Em '{finding['file']}'"
                    if 'line' in finding: location += f" (linha {finding['line']})"
                    click.echo(location)
                if 'details' in finding:
                    click.echo(Fore.CYAN + f"   > {finding['details']}")

    error_count = results['summary']['errors']
    warning_count = results['summary']['warnings']
    click.echo(Style.BRIGHT + "\n" + "-"*40)
    if error_count == 0 and warning_count == 0:
        click.echo(Fore.GREEN + "[OK] Análise concluída. Nenhum problema encontrado!")
    else:
        summary_text = f"[FIM] Análise concluída: {Fore.RED}{error_count} Erro(s){Style.RESET_ALL}, {Fore.YELLOW}{warning_count} Aviso(s){Style.RESET_ALL}."
        click.echo(summary_text)

def _analyze_traceback(stderr_output):
    """Analisa a saída de erro (stderr) e imprime um diagnóstico formatado."""
    diagnostics = {
        "ModuleNotFoundError": "[Ref: OTRAN-Bug#2] Erro de importação. Causas: lib não instalada no venv; conflito de versão.",
        "ImportError": "[Ref: OTRAN-Bug#2] Erro de importação. Causas: lib não instalada no venv; conflito de versão.",
        "AttributeError": "[Ref: DXTS-Bug#1] Erro de atributo. Causas: erro de digitação; API mudou; widget de GUI acessado antes da criação.",
        "FileNotFoundError": "[Ref: ORI-Bug#6] Arquivo não encontrado. Causas: caminho incorreto; dependência de sistema faltando; erro de escape de '\\'.",
        "UnboundLocalError": "[Ref: DXTS-Bug] Variável local não definida. Causa: variável usada antes de receber valor (comum em blocos 'if').",
        "NameError": "[Ref: SCUX-Test] Nome não definido. Causas: erro de digitação; importação faltando.",
        "_tkinter.TclError": "[Ref: DXTS-Bug#4] Erro de Tcl/Tk (GUI). Causas: conflito de layout (pack vs grid); referência de imagem perdida."
    }
    click.echo(Fore.YELLOW + "\n--- [DIAGNÓSTICO] ---")
    for key, message in diagnostics.items():
        if key in stderr_output:
            click.echo(Fore.CYAN + message); return
    click.echo(Fore.CYAN + "Nenhum padrão de erro conhecido foi encontrado. Analise o traceback acima.")

if __name__ == '__main__':
    try:
        cli()
    except Exception as e:
        click.echo(Fore.RED + Style.BRIGHT + "\n--- ERRO FATAL INESPERADO ---")
        click.echo(Fore.WHITE + "A Doxoade encontrou um erro interno. Um registro detalhado foi salvo no log.")
        
        # Criamos um registro de log forense completo
        results = {
            'summary': {'errors': 1, 'warnings': 0},
            'findings': [{
                'type': 'FATAL_ERROR',
                'message': 'A Doxoade encontrou um erro fatal interno e foi encerrada.',
                'details': str(e),
                'traceback': traceback.format_exc() # A chave para o diagnóstico completo
            }]
        }
        
        _log_execution(command_name="FATAL", path=".", results=results, arguments={'raw_command': sys.argv})
        raise e