# doxoade/doxoade.py

#import ast, esprima, fnmatch, shutil, time, shlex, signal, tempfile, threading
#from bs4 import BeautifulSoup
#from io import StringIO
#from pyflakes import api as pyflakes_api

import traceback
import toml
import subprocess
import os, sys, re
#import json
import click
import pandas as pd
from datetime import datetime
#from pathlib import Path
from functools import wraps
from colorama import init as colorama_init, Fore, Style
from doxoade.database import get_db_connection

#from queue import Queue, Empty
#from datetime import datetime

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PARENT = os.path.dirname(PACKAGE_DIR)
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)

# --- REGISTRO DE PLUGINS DA V2.0 ---
from doxoade.database import init_db
from doxoade.commands.webcheck import webcheck
from doxoade.commands.utils import log, show_trace, mk, create_pipeline, setup_regression
from doxoade.commands.tutorial import tutorial_group
from doxoade.commands.self_test import self_test
from doxoade.commands.save import save
from doxoade.commands.run import run
from doxoade.commands.regression_test import regression_test
from doxoade.commands.rebuild import rebuild
from doxoade.commands.optimize import optimize
from doxoade.commands.kvcheck import kvcheck
from doxoade.commands.intelligence import intelligence
from doxoade.commands.init import init
from doxoade.commands.health import health
from doxoade.commands.guicheck import guicheck
from doxoade.commands.global_health import global_health
from doxoade.commands.git_workflow import release, sync
from doxoade.commands.git_new import git_new
from doxoade.commands.git_clean import git_clean
from doxoade.commands.encoding import encoding
from doxoade.commands.doctor import doctor
from doxoade.commands.diff import diff
from doxoade.commands.deepcheck import deepcheck
from doxoade.commands.config import config_group
from doxoade.commands.clean import clean
from doxoade.commands.check import check
from doxoade.commands.canonize import canonize
from doxoade.commands.auto import auto
from doxoade.commands.apicheck import apicheck

from doxoade.shared_tools import (
    ExecutionLogger, 
#    _get_venv_python_executable, 
#    _present_results, 
    _log_execution, 
    _run_git_command, 
#    _load_config, 
#    _update_summary_from_findings,
#    _get_code_snippet
)

colorama_init(autoreset=True)

__version__ = "35.0 Alfa"


# -----------------------------------------------------------------------------
# GRUPO PRINCIPAL E CONFIGURAÇÃO
# -----------------------------------------------------------------------------

#atualizado em 2025/09/26-Versão 10.8. Adicionado tratamento de exceção global para garantir que falhas internas da ferramenta sejam sempre registradas no log.
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """olDox222 Advanced Development Environment (doxoade) LITE v1.0"""
    try:
        init_db()
    except Exception as e:
        click.echo(Fore.RED + f"Falha crítica na inicialização do banco de dados: {e}")
        raise e

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

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

#atualizado em 2025/09/25-Versão 9.1. Novo comando 'dashboard' para visualizar tendências de saúde do projeto a partir dos logs.
@cli.command()
@click.option('--project', default=None, help="Filtra o dashboard para um projeto específico.")
def dashboard(project):
    """Exibe um painel com a saúde e tendências dos projetos a partir do banco de dados."""
    click.echo(Fore.CYAN + Style.BRIGHT + "--- [DASHBOARD] Painel de Saúde de Engenharia (Projeto Sapiens) ---")

    try:
        conn = get_db_connection()
        
        # Constrói a query base
        query = "SELECT e.timestamp, e.project_path, f.severity, f.message FROM events e JOIN findings f ON e.id = f.event_id"
        params = []
        if project:
            query += " WHERE e.project_path = ?"
            params.append(os.path.abspath(project))
            
        # Usa o pandas para carregar os dados diretamente da query
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            click.echo(Fore.YELLOW + "Nenhum 'finding' encontrado no banco de dados para o filtro especificado.")
            return

        click.echo(f"Analisando {len(df)} findings registrados...\n")
        
        # Converte o timestamp para datetime para análise
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        _display_error_trend_db(df)
        _display_project_summary_db(df)
        _display_common_issues_db(df)

    except Exception as e:
        click.echo(Fore.RED + f"Erro ao gerar o dashboard: {e}")

def _display_error_trend_db(df):
    """Exibe a tendência de problemas a partir de um DataFrame."""
    click.echo(Fore.YELLOW + "--- Tendência de Problemas (últimos 7 dias) ---")
    df['day'] = df['timestamp'].dt.date
    recent_df = df[df['day'] >= (datetime.now().date() - pd.Timedelta(days=7))]
    
    issues_by_day = recent_df.groupby('day')['severity'].value_counts().unstack(fill_value=0)
    
    for day, row in issues_by_day.iterrows():
        errors = row.get('ERROR', 0) + row.get('CRITICAL', 0)
        warnings = row.get('WARNING', 0)
        click.echo(f"{day} | {Fore.RED}{errors} Erro(s){Style.RESET_ALL}, {Fore.YELLOW}{warnings} Aviso(s){Style.RESET_ALL}")

def _display_project_summary_db(df):
    """Exibe quais projetos têm mais problemas a partir de um DataFrame."""
    click.echo(Fore.YELLOW + "\n--- Projetos com Mais Erros Registrados ---")
    df['project_name'] = df['project_path'].apply(os.path.basename)
    error_df = df[df['severity'].isin(['ERROR', 'CRITICAL'])]
    
    errors_by_project = error_df.groupby('project_name').size().sort_values(ascending=False).head(5)
    
    for proj, count in errors_by_project.items():
        click.echo(f" - {proj}: {count} erros")

def _display_common_issues_db(df):
    """Exibe os tipos de erro mais comuns a partir de um DataFrame."""
    click.echo(Fore.YELLOW + "\n--- Tipos de Erro Mais Comuns ---")
    error_df = df[df['severity'].isin(['ERROR', 'CRITICAL'])].copy()
    
    # Extrai a mensagem principal antes de dois pontos ou parênteses
    error_df.loc[:, 'message_type'] = error_df['message'].str.split('[:(]').str[0].str.strip()
    
    errors_by_type = error_df.groupby('message_type').size().sort_values(ascending=False).head(5)
    
    for msg_type, count in errors_by_type.items():
        click.echo(f" - {msg_type}: {count} ocorrências")
        
# (Substitua a função setup_health inteira)
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 3.0(Fnc).
# Descrição: CORREÇÃO DE LÓGICA. A sequência de operações foi corrigida para garantir
# que a lista 'keep' seja criada e populada corretamente antes de salvar.
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

    click.echo(Fore.YELLOW + "\n--- 2. Verificando 'pyproject.toml'... ---")
    pyproject_path = os.path.join(path, 'pyproject.toml')
    
    try:
        if os.path.exists(pyproject_path):
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                toml_data = toml.load(f)
        else:
            toml_data = {}
    except toml.TomlDecodeError:
        logger.add_finding('error', "Arquivo 'pyproject.toml' corrompido.")
        click.echo(Fore.RED + "[ERRO] Seu 'pyproject.toml' parece corrompido."); sys.exit(1)

    tool_table = toml_data.setdefault('tool', {})
    doxoade_config = tool_table.setdefault('doxoade', {})
    
    # Garante os valores padrão
    doxoade_config.setdefault('ignore', [])
    current_source_dir = doxoade_config.setdefault('source_dir', '.')

    # Atualiza a lista 'keep'
    packages_to_keep = set(doxoade_config.setdefault('keep', []))
    health_tools = {"pytest", "coverage", "radon"}
    packages_to_keep.update(health_tools)
    doxoade_config['keep'] = sorted(list(packages_to_keep))
    
    # Pergunta sobre o source_dir
    new_source_dir = click.prompt("Diretório do código-fonte?", default=current_source_dir)
    doxoade_config['source_dir'] = new_source_dir
    
    # Salva o arquivo
    try:
        with open(pyproject_path, 'w', encoding='utf-8') as f:
            toml.dump(toml_data, f)
        click.echo(Fore.GREEN + "[OK] 'pyproject.toml' configurado e atualizado com a lista 'keep'.")
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

#atualizado em 2025/10/24-Versão 34.0.
# --- REGISTRO DE PLUGINS ---
cli.add_command(apicheck)
cli.add_command(auto)
cli.add_command(canonize)
cli.add_command(check)
cli.add_command(clean)
cli.add_command(config_group)
cli.add_command(create_pipeline)
cli.add_command(deepcheck)
cli.add_command(diff)
cli.add_command(doctor)
cli.add_command(encoding)
cli.add_command(git_clean)
cli.add_command(git_new)
cli.add_command(global_health)
cli.add_command(guicheck)
cli.add_command(health)
cli.add_command(init)
cli.add_command(intelligence)
cli.add_command(kvcheck)
cli.add_command(log)
cli.add_command(mk)
cli.add_command(optimize)
cli.add_command(rebuild)
cli.add_command(regression_test)
cli.add_command(release)
cli.add_command(run)
cli.add_command(save)
cli.add_command(self_test)
cli.add_command(setup_regression)
cli.add_command(show_trace)
cli.add_command(sync)
cli.add_command(tutorial_group)
cli.add_command(webcheck)

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