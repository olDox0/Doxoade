# doxoade/doxoade.py

#import ast, esprima, fnmatch, shutil, time, shlex, signal, tempfile, threading
#from bs4 import BeautifulSoup
#from io import StringIO
#from pyflakes import api as pyflakes_api

import click
import json
import os, sys, re
import subprocess
import toml
import traceback
#from queue import Queue, Empty
from pathlib import Path
from functools import wraps
from colorama import init as colorama_init, Fore, Style
from datetime import datetime

# --- REGISTRO DE PLUGINS DA V2.0 ---
from .commands.apicheck import apicheck
from .commands.check import check
from .commands.clean import clean
from .commands.deepcheck import deepcheck
from .commands.encoding import encoding
from .commands.git_clean import git_clean
from .commands.git_new import git_new
from .commands.guicheck import guicheck
from .commands.health import health
from .commands.init import init
from .commands.kvcheck import kvcheck
from .commands.optimize import optimize
from .commands.run import run
from .commands.save import save
from .commands.webcheck import webcheck
from .commands.tutorial import tutorial_group
from .commands.doctor import doctor
from .commands.auto import auto
from .commands.git_workflow import release, sync

from .shared_tools import (
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
cli.add_command(apicheck)
cli.add_command(check)
cli.add_command(clean)
cli.add_command(deepcheck)
cli.add_command(encoding)
cli.add_command(git_clean)
cli.add_command(git_new)
cli.add_command(guicheck)
cli.add_command(health)
cli.add_command(init)
cli.add_command(kvcheck)
cli.add_command(optimize)
cli.add_command(run)
cli.add_command(save)
cli.add_command(webcheck)
cli.add_command(tutorial_group)
cli.add_command(doctor)
cli.add_command(auto)
cli.add_command(release)
cli.add_command(sync)

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