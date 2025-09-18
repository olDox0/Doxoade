import threading
import queue
import time
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
from bs4 import BeautifulSoup
from io import StringIO
from colorama import init, Fore, Style
from pyflakes import api as pyflakes_api
from pathlib import Path
from datetime import datetime, timezone

# Inicializa o colorama para funcionar no Windows
init(autoreset=True)

# -----------------------------------------------------------------------------
# GRUPO PRINCIPAL E CONFIGURAÇÃO
# -----------------------------------------------------------------------------

@click.group()
def cli():
    """olDox222 Advanced Development Environment (doxoade) LITE v1.0"""
    pass

def _load_config():
    """Procura e carrega configurações de um arquivo .doxoaderc."""
    config = configparser.ConfigParser()
    config.read('.doxoaderc')
    settings = {'ignore': []}
    if 'doxoade' in config:
        ignore_str = config['doxoade'].get('ignore', '')
        settings['ignore'] = [line.strip() for line in ignore_str.split('\n') if line.strip()]
    return settings

# -----------------------------------------------------------------------------
# COMANDOS DA CLI (ARQUITETURA FINAL E ROBUSTA)
# -----------------------------------------------------------------------------

#atualizado em 2025/09/18-V41. Novo comando 'git-clean' para remover arquivos rastreados que correspondem ao .gitignore.
@cli.command('git-clean')
def git_clean():
    """Força a remoção de arquivos já rastreados que deveriam ser ignorados."""
    click.echo(Fore.CYAN + "--- [GIT-CLEAN] Procurando por arquivos rastreados indevidamente ---")
    
    gitignore_path = '.gitignore'
    if not os.path.exists(gitignore_path):
        click.echo(Fore.RED + "[ERRO] Arquivo .gitignore não encontrado no diretório atual.")
        sys.exit(1)

    # 1. Obter a lista de padrões do .gitignore
    with open(gitignore_path, 'r') as f:
        ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    # 2. Obter a lista de TODOS os arquivos rastreados pelo Git
    tracked_files_str = _run_git_command(['ls-files'], capture_output=True)
    if tracked_files_str is None:
        sys.exit(1)
    tracked_files = tracked_files_str.splitlines()

    # 3. Encontrar os arquivos que correspondem aos padrões
    files_to_remove = []
    for pattern in ignore_patterns:
        # Lida com padrões de diretório como 'venv/'
        if pattern.endswith('/'):
            pattern += '*'
        
        # fnmatch é perfeito para comparar nomes de arquivos com padrões do gitignore
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
        # Remove os arquivos um por um para mais segurança
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

#atualizado em 2025/09/17-V40. 'save' agora usa 'git commit -a' para respeitar os arquivos removidos do índice.
@cli.command()
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo que o 'check' encontre avisos ou apenas o erro de ambiente.")
def save(message, force):
    """Executa 'check', adiciona todos os arquivos modificados e faz um commit seguro."""
    click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")
    
    click.echo(Fore.YELLOW + "\nPasso 1: Executando 'doxoade check' para garantir a qualidade do código...")
    
    python_executable = sys.executable
    check_command = [python_executable, '-m', 'doxoade.doxoade', 'check', '.']
    check_result = subprocess.run(check_command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    output = check_result.stdout
    has_errors = check_result.returncode != 0
    has_warnings = "Aviso(s)" in output and "0 Aviso(s)" not in output
    is_only_env_error = has_errors and "1 Erro(s)" in output and "Ambiente Inconsistente" in output

    # --- LÓGICA DE DECISÃO ---
    
    # 1. Verifica se há erros bloqueantes
    if has_errors and not (force and is_only_env_error):
        click.echo(Fore.RED + "\n[ERRO] 'doxoade check' encontrou erros críticos. O salvamento foi abortado.")
        click.echo(Fore.WHITE + "Por favor, corrija os erros abaixo antes de salvar (ou use --force para ignorar apenas o erro de ambiente):")
        print(output)
        sys.exit(1)

    # 2. Se passamos, verifica se há avisos
    if has_warnings and not force:
        click.echo(Fore.YELLOW + "\n[AVISO] 'doxoade check' encontrou avisos.")
        if not click.confirm("Deseja continuar com o salvamento mesmo assim?"):
            click.echo("Salvamento abortado pelo usuário.")
            sys.exit(0)
    
    # Se chegamos até aqui, o caminho está livre
    if force and is_only_env_error:
        click.echo(Fore.YELLOW + "\n[AVISO] Erro de ambiente ignorado devido ao uso da flag --force.")
    
    click.echo(Fore.GREEN + "[OK] Verificação de qualidade concluída.")
    
    # --- LÓGICA DO GIT CORRIGIDA ---
    click.echo(Fore.YELLOW + "\nPasso 2: Verificando se há alterações para salvar...")
    status_output = _run_git_command(['status', '--porcelain'], capture_output=True)
    if status_output is None: sys.exit(1)
        
    if not status_output:
        click.echo(Fore.GREEN + "[OK] Nenhuma alteração nova para salvar. A árvore de trabalho está limpa.")
        return

    click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit com a mensagem: '{message}'...")
    # A MUDANÇA CRUCIAL: Usamos 'commit -a'.
    # '-a' automaticamente "adiciona" (stages) todos os arquivos que já estão sendo rastreados
    # e que foram modificados, e também respeita os arquivos que foram removidos com 'git rm'.
    # Ele não adiciona arquivos novos, o que é um comportamento seguro.
    if not _run_git_command(['commit', '-a', '-m', message]):
        
        # Fallback para o caso de haver arquivos novos que precisam ser adicionados
        click.echo(Fore.YELLOW + "Tentativa inicial de commit falhou (pode haver arquivos novos). Tentando com 'git add .'...")
        if not _run_git_command(['add', '.']): sys.exit(1)
        if not _run_git_command(['commit', '-m', message]): sys.exit(1)
    click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso no repositório!")

#atualizado em 2025/09/17-V38. 'init' agora cria o ramo 'main' por padrão para alinhar com as práticas modernas do Git.
@cli.command()
@click.argument('project_name', required=False)
def init(project_name):
    """Cria a estrutura inicial de um novo projeto Python, incluindo um repositório Git."""
    click.echo(Fore.CYAN + "--- [INIT] Assistente de Criação de Novo Projeto (doxoade init) ---")
    
    if not project_name:
        project_name = click.prompt("Qual é o nome do seu novo projeto?")
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        click.echo(Fore.RED + "[ERRO] Erro: O nome do projeto deve conter apenas letras, números, hífens e underscores."); return
    
    project_path = os.path.abspath(project_name)
    if os.path.exists(project_path):
        click.echo(Fore.RED + f"[ERRO] Erro: O diretório '{project_path}' já existe."); return
        
    original_dir = os.getcwd()
    
    try:
        click.echo(f"   > Criando a estrutura do projeto em: {project_path}")
        os.makedirs(project_path)
        
        click.echo("   > Criando ambiente virtual 'venv'...")
        python_executable = sys.executable
        subprocess.run([python_executable, "-m", "venv", os.path.join(project_path, "venv")], check=True, capture_output=True)

        click.echo("   > Criando arquivo .gitignore...")
        gitignore_content = ("venv/\n\n__pycache__/\n*.py[cod]\n\nbuild/\ndist/\n*.egg-info/\n\n.vscode/\n.idea/\n\n.env\n")
        with open(os.path.join(project_path, ".gitignore"), "w", encoding="utf-8") as f: f.write(gitignore_content)
        
        click.echo("   > Criando arquivo requirements.txt...")
        with open(os.path.join(project_path, "requirements.txt"), "w", encoding="utf-8") as f: f.write("# Adicione suas dependências aqui\n")
        
        click.echo("   > Criando arquivo main.py inicial...")
        main_py_content = ("def main():\n    print(\"Olá, do seu novo projeto!\")\n\nif __name__ == '__main__':\n    main()\n")
        with open(os.path.join(project_path, "main.py"), "w", encoding="utf-8") as f: f.write(main_py_content)

        click.echo("   > Inicializando repositório Git...")
        os.chdir(project_path)
        if _run_git_command(['init', '-b', 'main']):
            click.echo(Fore.GREEN + "     - Repositório Git criado com sucesso no ramo 'main'.")
        else:
            return

        click.echo(Fore.GREEN + "\n[INIT] Projeto criado com sucesso!")
        click.echo(Fore.YELLOW + "Próximos passos:")
        click.echo(f"1. Navegue até a pasta do seu projeto: cd {project_name}")
        click.echo("2. Configure seu repositório remoto (ex: no GitHub) e adicione-o:")
        click.echo(Fore.CYAN + "   git remote add origin URL_DO_SEU_REPOSITORIO.git")
        click.echo("3. Ative o ambiente virtual: .\\venv\\Scripts\\activate")

    except subprocess.CalledProcessError as e:
        click.echo(Fore.RED + f"[ERRO] Erro ao criar venv: {e.stderr.decode('utf-8', 'ignore')}")
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado: {e}")
    finally:
        os.chdir(original_dir)

#atualizado em 2025/09/16-V29. 'auto' agora invoca 'doxoade' como um módulo ('python -m doxoade') para garantir a propagação correta do código de saída e corrigir o bug do "sucesso falso".
@cli.command()
@click.argument('commands', nargs=-1, required=True)
def auto(commands):
    """Executa uma sequência completa de comandos e reporta o status de cada um."""
    total_commands = len(commands)
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [AUTO] Iniciando sequência de {total_commands} comando(s) ---")
    results = []
    try:
        for i, command_str in enumerate(commands, 1):
            click.echo(Fore.CYAN + f"\n--- [AUTO] Executando Passo {i}/{total_commands}: {command_str} ---")
            step_result = {"command": command_str, "status": "sucesso", "returncode": 0}
            try:
                args = shlex.split(command_str)
                if args and args[0] == 'doxoade':
                    python_executable = sys.executable
                    command_to_run = [python_executable, '-m', 'doxoade.doxoade'] + args[1:]
                    use_shell = False
                else:
                    command_to_run = command_str
                    use_shell = True
                
                process_result = subprocess.run(
                    command_to_run, shell=use_shell, text=True, encoding='utf-8', 
                    errors='replace', capture_output=True
                )
                if process_result.stdout: print(process_result.stdout)
                if process_result.stderr: print(process_result.stderr, file=sys.stderr)
                if process_result.returncode != 0:
                    step_result["status"] = "falha"
                    step_result["returncode"] = process_result.returncode
            except Exception as e:
                step_result["status"] = "falha"; step_result["error"] = str(e)
            results.append(step_result)
    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n [AUTO] Sequência cancelada pelo usuário (CTRL+C).")
        sys.exit(1)
        
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- [AUTO] Sumário da Sequência de Automação ---")
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
        click.echo(Fore.GREEN + Style.BRIGHT + "[AUTO] Sequência completa executada com sucesso!")
    else:
        click.echo(Fore.RED + Style.BRIGHT + "[ATENÇÃO] Sequência executada, mas um ou mais passos falharam.")
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

#atualizado em 2025/09/16-V31. Corrigido bug do "erro suave" garantindo sys.exit(1) no bloco de exceção.
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('script_and_args', nargs=-1, type=click.UNPROCESSED)
def run(script_and_args):
    """Executa um script Python garantindo o uso do venv correto."""
    if not script_and_args:
        click.echo(Fore.RED + "[ERRO] Erro: Nenhum script especificado para executar.", err=True); return
    
    script_name = script_and_args[0]
    if not os.path.exists(script_name):
        click.echo(Fore.RED + f"[ERRO] Erro: Não foi possível encontrar o script '{script_name}'.");
        click.echo(Fore.CYAN + "   > Verifique se o nome e o caminho para o arquivo estão corretos."); return
        
    venv_path = 'venv'
    python_executable = os.path.join(venv_path, 'Scripts', 'python.exe') if os.name == 'nt' else os.path.join(venv_path, 'bin', 'python')
    if not os.path.exists(python_executable):
        click.echo(Fore.RED + f"[ERRO] Erro: Ambiente virtual não encontrado em '{python_executable}'.", err=True); return
        
    command_to_run = [python_executable] + list(script_and_args)
    click.echo(Fore.CYAN + f"-> Executando '{' '.join(script_and_args)}' com o interpretador do venv...")
    click.echo(Fore.YELLOW + f"   (Caminho do Python: {python_executable})")
    click.echo("-" * 40)
    
    process = None
    full_stderr = ""

    try:
        process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        
        # Filas para comunicação entre os threads e o fio principal
        q_stdout = queue.Queue()
        q_stderr = queue.Queue()

        # Cria e inicia os threads para ler a saída em segundo plano
        stdout_thread = threading.Thread(target=_stream_reader, args=(process.stdout, q_stdout), daemon=True)
        stderr_thread = threading.Thread(target=_stream_reader, args=(process.stderr, q_stderr), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        # Loop principal: Fica vivo e responsivo enquanto o processo filho roda
        while process.poll() is None:
            try:
                # Exibe a saída em tempo real sem bloquear
                while not q_stdout.empty():
                    print(q_stdout.get_nowait(), end='')
                while not q_stderr.empty():
                    line = q_stderr.get_nowait()
                    full_stderr += line
                    print(Fore.RED + line, end='', file=sys.stderr)
            except queue.Empty:
                pass
            time.sleep(0.1) # Pequena pausa para não consumir 100% de CPU

        # Garante que os threads terminaram antes de prosseguir
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
        return_code = process.returncode

    except KeyboardInterrupt:
        click.echo("\n" + Fore.YELLOW + "[RUN] Interrupção detectada (CTRL+C). Encerrando o script filho...")
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
                click.echo(Fore.YELLOW + "Script encerrado.")
            except subprocess.TimeoutExpired:
                click.echo(Fore.RED + "O script não respondeu. Forçando o encerramento (kill).", err=True)
                process.kill()
        return_code = 130
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado ao executar o script: {e}", err=True)
        sys.exit(1)
    finally:
        if process and process.poll() is None:
            process.kill() # Garante que nenhum processo zumbi seja deixado para trás

    click.echo("-" * 40)
    if return_code != 0 or full_stderr:
        if full_stderr: _analyze_traceback(full_stderr)
        click.echo(Fore.RED + f"[ERRO] O script '{script_name}' terminou com um erro ou avisos (código {return_code}).")
    else:
        click.echo(Fore.GREEN + f"[OK] Script '{script_name}' finalizado com sucesso.")

@cli.command()
@click.option('--force', '-f', is_flag=True, help="Força a limpeza sem pedir confirmação.")
def clean(force):
    """Remove arquivos de cache e build (__pycache__, build/, dist/, *.spec)."""
    TARGET_DIRS = ["__pycache__", "build", "dist", ".pytest_cache", ".tox"]
    TARGET_PATTERNS = [re.compile(r".*\.egg-info$"), re.compile(r".*\.spec$")]
    click.echo(Fore.CYAN + "-> [CLEAN] Procurando por artefatos de build e cache...")
    targets_to_delete = []
    for root, dirs, files in os.walk('.', topdown=True):
        dirs[:] = [d for d in dirs if 'venv' in d]
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

#atualizado em 2025/09/17-V37. Corrigido TypeError ao garantir que a saída de erro do Git seja sempre uma string.
def _run_git_command(args, capture_output=False):
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
        click.echo(Fore.RED + "[ERRO GIT] O comando 'git' não foi encontrado. O Git está instalado e no PATH do sistema?")
        return None
    except subprocess.CalledProcessError as e:
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
    
#atualizado em 2025/09/16-V24. Função trabalhadora para ler streams de I/O em um thread separado de forma não-bloqueante.
def _stream_reader(stream, q):
    """Lê linhas de um stream e as coloca em uma fila."""
    for line in iter(stream.readline, ''):
        q.put(line)
    stream.close()

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

#atualizado em 2025/09/16-V31. Corrigido DeprecationWarning e bug de encoding.
def _log_execution(command_name, path, results, arguments):
    """Constrói o log detalhado e o anexa ao arquivo de log."""
    try:
        log_dir = Path.home() / '.doxoade'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'doxoade.log'
        
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Prepara a lista detalhada de findings para o log
        detailed_findings = []
        for category, findings_list in results.items():
            if category == 'summary':
                continue
            for finding in findings_list:
                # Cria uma cópia para não modificar o dicionário original
                finding_copy = finding.copy()
                # Adiciona a categoria a cada finding para contextualização no log
                finding_copy['category'] = category
                detailed_findings.append(finding_copy)
        
        log_data = {
            "timestamp": timestamp,
            "command": command_name,
            "project_path": os.path.abspath(path),
            "arguments": arguments,
            "summary": results.get('summary', {}), # Pega o sumário do results
            "status": "completed",
            "findings": detailed_findings # Adiciona a lista detalhada
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_data) + '\n')

    except Exception as e:
        click.echo(Fore.RED + f"\n[AVISO DE LOG] Não foi possível escrever no arquivo de log detalhado: {e}", err=True)

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
    
def _check_source_code(path, ignore_list=None, fix_errors=False, text_format=True):
    """Analisa arquivos .py e retorna uma lista de problemas."""
    findings = []
    folders_to_ignore = set([item.lower() for item in ignore_list or []] + ['venv', 'build', 'dist'])
    files_to_check = []
    for root, dirs, files in os.walk(path):
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
                    line_num = 'N/A'
                    message_text = line_error

                if "' imported but unused" in message_text and fix_errors:
                    lines_to_remove.add(line_num)
                else:
                    finding = {
                        'type': 'error', 
                        'message': message_text, 
                        'ref': 'Pyflakes', 
                        'file': file_path, 
                        'line': line_num
                    }
                    # Adiciona o snippet com contexto ao redor da linha do erro
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
    folders_to_ignore = set([item.lower() for item in ignore_list or []] + ['venv', 'build', 'dist'])
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

def _check_gui_files(path, ignore_list=None):
    """Analisa arquivos Python de GUI e retorna uma lista de problemas."""
    folders_to_ignore = set([item.lower() for item in ignore_list or []] + ['venv', 'build', 'dist'])
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
        findings.extend(_check_gui_events(file_path))
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

def _check_gui_events(file_path):
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
    cli()