# doxoade/doxoade.py
#import ast, esprima, fnmatch
#from bs4 import BeautifulSoup
#from io import StringIO
#from pyflakes import api as pyflakes_api
import json
import os, sys, re
import shutil   
import subprocess
import click
import shlex
import traceback
import time
import tempfile
import threading
import signal
import toml
from queue import Queue, Empty
from pathlib import Path
from functools import wraps
from colorama import init, Fore, Style
from datetime import datetime

# --- REGISTRO DE PLUGINS DA V2.0 ---
from .commands.optimize import optimize
from .commands.health import health
from .commands.check import check
from .commands.guicheck import guicheck
from .commands.webcheck import webcheck
from .commands.kvcheck import kvcheck
from .commands.encoding import encoding
from .commands.apicheck import apicheck
from .commands.deepcheck import deepcheck
from .commands.save import save
from .commands.git_clean import git_clean

from .shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
#    _present_results, 
    _log_execution, 
    _run_git_command, 
#    _load_config, 
#    _update_summary_from_findings,
#    _get_code_snippet
)

init(autoreset=True)

__version__ = "35.0 Alfa"

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

def log_command_execution(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        command_name = ctx.command.name
        path = kwargs.get('path', '.')
        results = {'summary': {'errors': 0, 'warnings': 0}}
        try:
            return func(*args, **kwargs)
        except Exception:
            raise
        finally:
            # Converte qualquer valor não-serializável para string
            serializable_kwargs = {k: str(v) for k, v in kwargs.items()}
            _log_execution(command_name, path, results, serializable_kwargs)
    return wrapper

# -----------------------------------------------------------------------------
# COMANDOS DA CLI (ARQUITETURA FINAL E ROBUSTA)
# -----------------------------------------------------------------------------

#atualizado em 2025/09/24-Versão 8.0. Novo comando 'doctor' para meta-análise da própria ferramenta. Tem como função verificar o ambiente, as dependências internas e a qualidade do código da doxoade.
@cli.command()
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
@click.option('--project', default=None, help="Filtra o dashboard para um projeto específico.")
def dashboard(project):
    #2025/10/11 - 34.0(Ver), 2.0(Fnc). Refatorada para reduzir complexidade e adicionar novos insights.
    #A função tem como objetivo exibir um painel com a saúde e tendências dos projetos analisados.
    log_file = Path.home() / '.doxoade' / 'doxoade.log'
    if not log_file.exists():
        click.echo(Fore.YELLOW + "Nenhum arquivo de log encontrado."); return

    click.echo(Fore.CYAN + Style.BRIGHT + "--- [DASHBOARD] Painel de Saúde de Engenharia ---")

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            entries = [json.loads(line) for line in f]
    except (json.JSONDecodeError, IOError):
        click.echo(Fore.RED + "Erro ao ler o arquivo de log."); return

    if project:
        entries = [e for e in entries if os.path.abspath(project) == e.get('project_path')]

    if not entries:
        click.echo(Fore.RED + "Nenhuma entrada de log encontrada para o filtro especificado."); return

    click.echo(f"Analisando {len(entries)} execuções registradas...\n")
    
    _display_error_trend(entries)
    _display_project_summary(entries)
    _display_common_issues(entries)

def _display_error_trend(entries):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo exibir a tendência de erros e avisos ao longo do tempo.
    issues_by_day = {}
    for entry in entries:
        day = entry.get('timestamp', 'N/A')[:10]
        summary = entry.get('summary', {})
        errors = summary.get('errors', 0)
        warnings = summary.get('warnings', 0)
        
        day_stats = issues_by_day.setdefault(day, {'errors': 0, 'warnings': 0})
        day_stats['errors'] += errors
        day_stats['warnings'] += warnings

    click.echo(Fore.YELLOW + "--- Tendência de Problemas (últimos 7 dias) ---")
    sorted_days = sorted(issues_by_day.keys())[-7:]
    for day in sorted_days:
        stats = issues_by_day[day]
        click.echo(f"{day} | {Fore.RED}{stats['errors']} Erro(s){Style.RESET_ALL}, {Fore.YELLOW}{stats['warnings']} Aviso(s){Style.RESET_ALL}")

def _display_project_summary(entries):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo exibir quais projetos têm mais problemas.
    errors_by_project = {}
    for entry in entries:
        proj_name = os.path.basename(entry.get('project_path', 'Desconhecido'))
        errors = entry.get('summary', {}).get('errors', 0)
        errors_by_project[proj_name] = errors_by_project.get(proj_name, 0) + errors
    
    click.echo(Fore.YELLOW + "\n--- Projetos com Mais Erros Registrados ---")
    sorted_projects = sorted(errors_by_project.items(), key=lambda item: item[1], reverse=True)[:5]
    for proj, count in sorted_projects:
        click.echo(f" - {proj}: {count} erros")

def _display_common_issues(entries):
    #2025/10/11 - 34.0(Ver), 1.0(Fnc). Nova função auxiliar.
    #A função tem como objetivo exibir os tipos de erro mais comuns.
    errors_by_type = {}
    for entry in entries:
        for finding in entry.get('findings', []):
            if finding.get('type', '').upper() == 'ERROR':
                msg = finding.get('message', 'Erro desconhecido').split(':')[0].strip()
                errors_by_type[msg] = errors_by_type.get(msg, 0) + 1
    
    click.echo(Fore.YELLOW + "\n--- Tipos de Erro Mais Comuns ---")
    sorted_types = sorted(errors_by_type.items(), key=lambda item: item[1], reverse=True)[:5]
    for msg_type, count in sorted_types:
        click.echo(f" - {msg_type}: {count} ocorrências")
        
#atualizado em 2025/10/07-Versão 31.3. Tem como função preparar um projeto para análise. Melhoria: A lógica de escrita foi refeita para sempre criar a diretiva 'ignore' como uma lista TOML, garantindo um parsing robusto e corrigindo o bug do 'ignore' não ser respeitado.
@cli.command('setup-health')
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.')
@click.pass_context
def setup_health(ctx, path):
    """Prepara um projeto para ser analisado pelo 'doxoade health'."""
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [SETUP-HEALTH] Configurando o projeto em '{path}' para análise de saúde ---")

    arguments = ctx.params
    with ExecutionLogger('setup-health', path, arguments) as logger:
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

    # --- Passo 2: Verificar e atualizar pyproject.toml (LÓGICA REFEITA) ---
    click.echo(Fore.YELLOW + "\n--- 2. Verificando 'pyproject.toml'... ---")
    pyproject_path = os.path.join(path, 'pyproject.toml')
    
    pyproject_data = {}
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                pyproject_data = toml.load(f)
        except toml.TomlDecodeError:
            logger.add_finding('error', "Arquivo 'pyproject.toml' corrompido.")
            click.echo(Fore.RED + "[ERRO] Seu 'pyproject.toml' parece corrompido."); sys.exit(1)

    # Garante a estrutura completa, incluindo 'ignore' como lista
    tool_table = pyproject_data.setdefault('tool', {})
    doxoade_table = tool_table.setdefault('doxoade', {})
    doxoade_table.setdefault('source_dir', '.')
    doxoade_table.setdefault('ignore', []) # Garante que 'ignore' seja uma lista

    current_source_dir = doxoade_table.get('source_dir', '.')
    new_source_dir = click.prompt("Diretório do código-fonte?", default=current_source_dir)
    doxoade_table['source_dir'] = new_source_dir
        
    try:
        with open(pyproject_path, 'w', encoding='utf-8') as f:
            toml.dump(pyproject_data, f)
        click.echo(Fore.GREEN + "[OK] 'pyproject.toml' configurado com '[tool.doxoade]'.")
    except Exception as e:
        logger.add_finding('error', f"Falha ao escrever no 'pyproject.toml': {e}")
        click.echo(Fore.RED + f"[ERRO] Falha ao escrever no 'pyproject.toml': {e}"); sys.exit(1)
    
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
@log_command_execution
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

#atualizado em 2025/10/05-Versão 28.7 (Arquitetura Final). Tem como função executar um pipeline. Melhoria: A arquitetura foi refeita para um modelo híbrido definitivo, usando Popen com shlex.split para comandos não-interativos e Run com isolamento de sinal para comandos interativos. Esta versão corrige todos os bugs de regressão de parsing e interrupção.
@cli.command()
@click.argument('commands', nargs=-1, required=True)
def auto(commands):
    """
    Executa uma sequência de comandos como um pipeline robusto.

    REGRA DE OURO (WINDOWS): Envolva o comando inteiro em aspas duplas "
    e use aspas simples ' para argumentos internos.

    Exemplo:
      doxoade auto "doxoade check --ignore-finding 'Ambiente Inconsistente'" "doxoade save 'Deploy final'"
    """
    if not commands:
        click.echo(Fore.YELLOW + "Nenhum comando para executar."); return

    total_commands = len(commands)
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando pipeline de {total_commands} passo(s) ---")
    
    # O tempfile é essencial para contornar o parsing inicial do cmd.exe
    with tempfile.NamedTemporaryFile(mode='w+', delete=True, suffix='.dox', encoding='utf-8') as temp_pipeline:
        for command in commands:
            temp_pipeline.write(f"{command}\n")
        temp_pipeline.flush()
        temp_pipeline.seek(0)
        commands_to_run = [line.strip() for line in temp_pipeline if line.strip() and not line.strip().startswith('#')]

    results = []
    original_sigint_handler = signal.getsignal(signal.SIGINT)

    try:
        for i, command_str in enumerate(commands_to_run, 1):
            click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{total_commands}: {command_str} ---")
            step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
            
            try:
                args = shlex.split(command_str)
                is_interactive = 'run' in args and 'doxoade' in args

                if is_interactive:
                    # --- ARQUITETURA INTERATIVA (CORRETA) ---
                    click.echo(Fore.YELLOW + "[AUTO] Comando interativo detectado. Cedendo controle...")
                    try:
                        signal.signal(signal.SIGINT, signal.SIG_IGN)
                        process_result = subprocess.run(command_str, shell=True, text=True, encoding='utf-8', errors='replace')
                    finally:
                        signal.signal(signal.SIGINT, original_sigint_handler)
                    
                    if process_result.returncode != 0:
                        step_result["status"] = "falha"; step_result["returncode"] = process_result.returncode
                else:
                    # --- ARQUITETURA NÃO-INTERATIVA (CORRETA) ---
                    process = subprocess.Popen(args, shell=True, text=True, encoding='utf-8', errors='replace',
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    def _stream_reader(pipe, color=None):
                        for line in iter(pipe.readline, ''):
                            output = color + line + Style.RESET_ALL if color else line
                            sys.stdout.write(output)

                    stdout_thread = threading.Thread(target=_stream_reader, args=[process.stdout])
                    stderr_thread = threading.Thread(target=_stream_reader, args=[process.stderr, Fore.RED])
                    stdout_thread.start(); stderr_thread.start()
                    process.wait(); stdout_thread.join(); stderr_thread.join()

                    if process.returncode != 0:
                        step_result["status"] = "falha"; step_result["returncode"] = process.returncode
            except Exception as e:
                step_result["status"] = "falha"; step_result["error"] = str(e)
            
            results.append(step_result)

    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n [AUTO] Pipeline cancelado pelo usuário.")
        sys.exit(1)
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)
        
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

#adicionado em 2025/10/02-Versão 25.0. Tem como função analisar e exibir um arquivo de trace de sessão. Melhoria: Encontra automaticamente o trace mais recente se nenhum arquivo for especificado.
@cli.command('show-trace')
@click.argument('filepath', type=click.Path(exists=True, dir_okay=False), required=False)
def show_trace(filepath):
    """Analisa e exibe um arquivo de trace de sessão (.jsonl) de forma legível."""
    
    target_file = filepath
    if not target_file:
        click.echo(Fore.CYAN + "Nenhum arquivo especificado. Procurando pelo trace mais recente...")
        target_file = _find_latest_trace_file()
        if not target_file:
            click.echo(Fore.RED + "Nenhum arquivo de trace ('doxoade_trace_*.jsonl') encontrado no diretório atual."); return
        click.echo(Fore.GREEN + f"Encontrado: '{target_file}'")

    click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TRACE REPLAY] Exibindo sessão de '{target_file}' ---")
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            click.echo(Fore.YELLOW + "O arquivo de trace está vazio."); return

        first_ts = json.loads(lines[0]).get('ts', 0)
        
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                stream = entry.get('stream', 'unknown')
                data = entry.get('data', '').rstrip('\n')
                
                relative_time = ts - first_ts
                
                color = Fore.YELLOW
                if stream == 'stdout': color = Fore.GREEN
                elif stream == 'stderr': color = Fore.RED
                
                click.echo(color + f"[{relative_time:8.3f}s] [{stream.upper():<6}] " + Style.RESET_ALL + data)

            except (json.JSONDecodeError, KeyError):
                click.echo(Fore.RED + f"[ERRO] Linha malformada no arquivo de trace: {line.strip()}")
                continue
                
    except Exception as e:
        click.echo(Fore.RED + f"Falha ao processar o arquivo de trace: {e}")

#atualizado em 2025/10/02-Versão 26.0. Melhoria: A busca pelo trace mais recente agora é feita no diretório centralizado (~/.doxoade/traces/).
def _find_latest_trace_file():
    """Encontra o arquivo de trace mais recente no diretório global de traces."""
    try:
        trace_dir = Path.home() / '.doxoade' / 'traces'
        if not trace_dir.exists():
            return None
            
        trace_files = list(trace_dir.glob('trace_*.jsonl'))
        if not trace_files:
            return None
            
        latest_file = max(trace_files, key=lambda p: p.stat().st_mtime)
        return str(latest_file)
    except Exception:
        return None

#atualizado em 2025/10/05-Versão 28.9. Tem como função executar scripts. Melhoria: Corrigido o NameError ao reordenar a criação do logger para o início da função, garantindo que ele esteja sempre disponível.
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('script_and_args', nargs=-1, type=click.UNPROCESSED)
@click.option('--trace', is_flag=True, help="Grava a sessão de I/O completa em um arquivo .trace.")
@click.pass_context
def run(ctx, script_and_args, trace):
    """Executa um script Python, suportando interatividade e gravação de sessão."""
    arguments = ctx.params

    if not script_and_args:
        click.echo(Fore.RED + "[ERRO] Nenhum script especificado.", err=True); sys.exit(1)
    
    script_name = script_and_args[0]
    
    with ExecutionLogger('run', '.', arguments) as logger:
        if not os.path.exists(script_name):
            msg = f"Script não encontrado: '{script_name}'."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}"); sys.exit(1)
            
        python_executable = _get_venv_python_executable()
        if not python_executable:
            msg = "Ambiente virtual 'venv' não encontrado."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}"); sys.exit(1)
            
        if trace:
            doxoade_dir = os.path.dirname(os.path.abspath(__file__))
            tracer_path = os.path.join(doxoade_dir, 'tracer.py')

            if not os.path.exists(tracer_path):
                logger.add_finding('error', "Módulo 'tracer.py' não encontrado na instalação da doxoade.")
                click.echo(Fore.RED + "[ERRO] Falha crítica: 'tracer.py' não encontrado.")
                sys.exit(1)
            command_to_run = [python_executable, '-u', tracer_path] + list(script_and_args)
        else:
            command_to_run = [python_executable, '-u'] + list(script_and_args)
        
        click.echo(Fore.CYAN + f"-> Executando '{' '.join(script_and_args)}' com o interpretador do venv...")
        if trace:
            click.echo(Fore.YELLOW + Style.BRIGHT + "   [MODO TRACE ATIVADO] A sessão será gravada.")
        click.echo("-" * 40)
        
        return_code = 1
        if trace:
            if os.name == 'nt':
                return_code = _run_traced_session_windows(command_to_run, logger)
            else:
                logger.add_finding('warning', "O modo --trace ainda não está implementado para plataformas não-Windows.")
                click.echo(Fore.YELLOW + "AVISO: --trace ainda não suportado neste SO. Executando em modo normal.")
                process = subprocess.Popen(command_to_run)
                process.wait()
                return_code = process.returncode
        else:
            try:
                process = subprocess.Popen(command_to_run)
                process.wait()
                return_code = process.returncode
            except KeyboardInterrupt:
                click.echo("\n" + Fore.YELLOW + "[RUN] Interrupção (CTRL+C).")
                return_code = 130
        
        click.echo("-" * 40)
        if return_code != 0:
            logger.add_finding('error', f"O script terminou com o código de erro {return_code}.")
            click.echo(Fore.RED + f"[ERRO] O script '{script_name}' terminou com o código de erro {return_code}.")
            sys.exit(1)
        else:
            click.echo(Fore.GREEN + f"[OK] Script '{script_name}' finalizado com sucesso.")

#atualizado em 2025/10/05-Versão 27.5 (Arquitetura Final). Tem como função gravar uma sessão. Melhoria: A arquitetura foi finalizada para suportar tanto scripts rápidos quanto interativos, reintroduzindo um 'writer thread' robusto para lidar com o 'stdin' e corrigindo o deadlock.
def _run_traced_session_windows(command, logger):
    """Executa um comando no Windows, gravando stdin, stdout e stderr."""
    trace_dir = Path.home() / '.doxoade' / 'traces'
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file_path = trace_dir / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )
        
        q_out = Queue()
        q_err = Queue()

        def _reader_thread(pipe, queue):
            try:
                for line in iter(pipe.readline, ''):
                    queue.put(line)
            finally:
                pipe.close()
        
        # --- WRITER THREAD REINTRODUZIDO E CORRIGIDO ---
        def _writer_thread(pipe, trace_f):
            try:
                for line in sys.stdin:
                    pipe.write(line)
                    pipe.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdin', 'data': line}
                    trace_f.write(json.dumps(log_entry) + '\n')
            except (IOError, OSError):
                # O stdin do processo filho foi fechado, o que é normal.
                pass

        threading.Thread(target=_reader_thread, args=[process.stdout, q_out], daemon=True).start()
        threading.Thread(target=_reader_thread, args=[process.stderr, q_err], daemon=True).start()
        
        with open(trace_file_path, 'w', encoding='utf-8') as trace_file:
            click.echo(Fore.YELLOW + f"   [TRACE] Gravando sessão em '{trace_file_path}'...")
            
            # Inicia o thread para lidar com a entrada do usuário
            threading.Thread(target=_writer_thread, args=[process.stdin, trace_file], daemon=True).start()

            # Loop principal de I/O
            while process.poll() is None:
                try:
                    line_out = q_out.get_nowait()
                    sys.stdout.write(line_out); sys.stdout.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdout', 'data': line_out}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                try:
                    line_err = q_err.get_nowait()
                    sys.stderr.write(Fore.RED + line_err); sys.stderr.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stderr', 'data': line_err}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                time.sleep(0.05)

            # Fase de Drenagem Final
            while not q_out.empty() or not q_err.empty():
                try:
                    line_out = q_out.get_nowait()
                    sys.stdout.write(line_out); sys.stdout.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdout', 'data': line_out}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                try:
                    line_err = q_err.get_nowait()
                    sys.stderr.write(Fore.RED + line_err); sys.stderr.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stderr', 'data': line_err}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass

        logger.add_finding('info', f"Sessão gravada com sucesso em '{trace_file_path}'.")
        return process.returncode

    except Exception as e:
        logger.add_finding('error', f"Falha na execução do trace: {e}")
        return 1

@cli.command()
@log_command_execution
@click.option('--force', '-f', is_flag=True, help="Força a limpeza sem pedir confirmação.")
def clean(force):
    #2025/10/11 - 34.0(Ver), 2.0(Fnc). Refatorada para reduzir complexidade.
    #A função tem como objetivo remover arquivos de cache e build.
    click.echo(Fore.CYAN + "-> [CLEAN] Procurando por artefatos de build e cache...")
    
    TARGET_PATTERNS = ["__pycache__", "build", "dist", ".pytest_cache", ".tox", "*.egg-info", "*.spec"]
    
    # Usamos Path.glob para encontrar todos os alvos de uma vez
    all_paths = [p for pattern in TARGET_PATTERNS for p in Path('.').rglob(pattern)]
    
    # Filtramos para garantir que não estamos deletando dentro de venv
    targets_to_delete = {p for p in all_paths if 'venv' not in p.parts and '.git' not in p.parts}

    if not targets_to_delete:
        click.echo(Fore.GREEN + "[OK] O projeto já está limpo."); return

    click.echo(Fore.YELLOW + f"Encontrados {len(targets_to_delete)} itens para remover:")
    for target in sorted(targets_to_delete): click.echo(f"  - {target}")

    if not force and not click.confirm(f"\n{Fore.YELLOW}Remover permanentemente estes itens?"):
        click.echo(Fore.CYAN + "\nOperação cancelada."); return

    click.echo(Fore.CYAN + "\n-> Iniciando a limpeza...")
    deleted_count = 0
    for target in sorted(targets_to_delete, reverse=True): # Deletamos do mais profundo para o mais raso
        try:
            if target.is_dir():
                shutil.rmtree(target)
                click.echo(f"  {Fore.RED}Removido diretório: {target}")
            elif target.is_file():
                target.unlink()
                click.echo(f"  {Fore.RED}Removido arquivo: {target}")
            deleted_count += 1
        except OSError as e:
            click.echo(Fore.RED + f"  Erro ao remover {target}: {e}", err=True)
    
    click.echo(Fore.GREEN + f"\n Limpeza concluída! {deleted_count} itens foram removidos.")
    
#atualizado em 2025/09/30-Versão 18.3. Tem como função escrever o log. Melhoria: Corrigido o bug crítico que impedia o salvamento dos 'findings'. A função agora consolida os resultados de todas as categorias de análise em uma única lista antes de salvar.
@cli.command()
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

#atualizado em 2025/10/01-Versão 18.7. Tem como função exibir uma entrada de log. Melhoria: Implementada a lógica de exibição para os snippets de código, que agora são mostrados quando a flag --snippets é usada.
def _display_log_entry(entry, index, total, show_snippets=False):
    """Formata e exibe uma única entrada de log de forma legível, com snippets opcionais."""
    try:
        ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
        ts_local = ts.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, KeyError):
        ts_local = entry.get('timestamp', 'N/A')

    header = f"--- Entrada de Log #{index}/{total} ({ts_local}) ---"
    click.echo(Fore.CYAN + Style.BRIGHT + header)

    # --- NOVO BLOCO: CONTEXTO FORENSE DA EXECUÇÃO ---
    click.echo(Fore.WHITE + f"Comando: {entry.get('command', 'N/A')} (Doxoade v{entry.get('doxoade_version', 'N/A')})")
    click.echo(Fore.WHITE + f"Projeto: {entry.get('project_path', 'N/A')}")
    
    context_line = (
        f"Contexto: "
        f"Git({entry.get('git_hash', 'N/A')[:7]}) | "
        f"Plataforma({entry.get('platform', 'N/A')}) | "
        f"Python({entry.get('python_version', 'N/A')}) | "
        f"Tempo({entry.get('execution_time_ms', 0):.2f}ms)"
    )
    click.echo(Fore.WHITE + Style.DIM + context_line)
    # ---------------------------------------------------
    
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
            f_color = Fore.RED if 'ERROR' in f_type else Fore.YELLOW
            f_msg = finding.get('message', 'N/A')
            f_file = finding.get('file', 'N/A')
            f_line = finding.get('line', '')
            f_ref = f" [Ref: {finding.get('ref')}]" if finding.get('ref') else ""
            
            click.echo(f_color + f"  - [{f_type}] {f_msg}{f_ref} (em {f_file}, linha {f_line})")

            # --- LÓGICA DE DETALHES COMPLETA ---
            if finding.get('details'):
                click.echo(Fore.CYAN + f"    > {finding.get('details')}")

            # --- LÓGICA DE EXIBIÇÃO DE SNIPPETS ---
            snippet = finding.get('snippet')
            if show_snippets and snippet:
                # Usamos .get() com um valor padrão para evitar erros se a linha não for um número
                f_line_int = int(finding.get('line', -1)) 
                for line_num_str, code_line in snippet.items():
                    line_num = int(line_num_str)
                    if line_num == f_line_int:
                        # Destaque para a linha do erro
                        click.echo(Fore.WHITE + Style.BRIGHT + f"      > {line_num:3}: {code_line}")
                    else:
                        # Contexto com menos destaque
                        click.echo(Fore.WHITE + Style.DIM + f"        {line_num:3}: {code_line}")
            # ----------------------------------------
    click.echo("")
    
# -----------------------------------------------------------------------------
# FUNÇÕES DE APRESENTAÇÃO E DIAGNÓSTICO
# -----------------------------------------------------------------------------

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


#atualizado em 2025/10/07-Versão 32.0. Melhoria: O núcleo agora registra comandos a partir de módulos de plugin externos.
# --- REGISTRO DE PLUGINS ---
cli.add_command(optimize)
cli.add_command(health)
cli.add_command(check)
cli.add_command(guicheck)
cli.add_command(webcheck)
cli.add_command(kvcheck)
cli.add_command(encoding)
cli.add_command(apicheck)
cli.add_command(deepcheck)
cli.add_command(save)
cli.add_command(git_clean)

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