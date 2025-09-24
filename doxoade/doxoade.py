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

#atualizado em 2025/09/23-Versão 5.5. Tutorial completamente reescrito para incluir todos os comandos da suíte (sync, release, clean, git-clean, guicheck) e melhorar a clareza para novos usuários.
@cli.command()
def tutorial():
    """Exibe um guia passo a passo do workflow completo do doxoade."""
    
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

#atualizado em 2025/09/23-Versão 5.2. Adicionados comandos 'release' e 'sync' para completar a suíte Git. Tem como função automatizar o versionamento e a sincronização com o repositório remoto. Melhoria: 'release' agora suporta a geração opcional de uma nota de release simples.
@cli.command()
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

#atualizado em 2025/09/23-Versão 5.4. Corrigido bug crítico onde 'sync' não executava 'git push'. Tem como função sincronizar o branch local com o remoto (puxar e empurrar). Melhoria: Adicionado '--no-edit' ao pull para evitar prompts de merge em scripts.
@cli.command()
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


#atualizado em 2025/09/18-V45. 'git-clean' agora lê o .gitignore com encoding='utf-8' explícito e lida com erros de decodificação.
@cli.command('git-clean')
def git_clean():
    """Força a remoção de arquivos já rastreados que correspondem ao .gitignore."""
    click.echo(Fore.CYAN + "--- [GIT-CLEAN] Procurando por arquivos rastreados indevidamente ---")
    
    gitignore_path = '.gitignore'
    if not os.path.exists(gitignore_path):
        click.echo(Fore.RED + "[ERRO] Arquivo .gitignore não encontrado no diretório atual.")
        sys.exit(1)

    try:
        with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
            ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Não foi possível ler o arquivo .gitignore: {e}")
        sys.exit(1)

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

    
#atualizado em 2025/09/17-V40. 'save' agora usa 'git commit -a' para respeitar os arquivos removidos do índice.
@cli.command()
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo que o 'check' encontre avisos ou apenas o erro de ambiente.")
def save(message, force):
    """
    Executa um "commit seguro", protegendo seu repositório de código com erros.

    Este comando é o coração do workflow do doxoade. Ele automatiza 3 passos:
    1. Executa 'doxoade check' para validar a qualidade do código.
    2. Se houver erros, o commit é abortado.
    3. Se tudo estiver OK, ele executa 'git commit -a -m "MESSAGE"'.

    Exemplos:
      doxoade save "Adicionada funcionalidade de login"
      doxoade save "Corrigido bug na validação de formulário" --force
    """
    # ...
    click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")
    click.echo(Fore.YELLOW + "\nPasso 1: Executando 'doxoade check' para garantir a qualidade do código...")
    
    # 1. Carrega a configuração do .doxoaderc
    config = _load_config()
    ignore_list = config.get('ignore', [])
    
    python_executable = sys.executable
    check_command = [python_executable, '-m', 'doxoade.doxoade', 'check', '.']
    
    # 2. Adiciona as flags --ignore ao comando
    for folder in ignore_list:
        check_command.extend(['--ignore', folder])

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

#atualizado em 2025/09/20-V48. Removido 'capture_output=True' para permitir o streaming de saída em tempo real dos comandos filhos, corrigindo o bug de "eco atrasado".
@cli.command()
@click.argument('commands', nargs=-1, required=True)
def auto(commands):
    """
    Executa uma sequência completa de comandos e reporta o status de cada um.
    
    Exemplo: doxoade auto "doxoade check ." "doxoade run main.py"
    """
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
                
                # --- CORREÇÃO APLICADA AQUI ---
                # Removemos capture_output=True. Agora a saída do filho vai direto para o terminal.
                process_result = subprocess.run(
                    command_to_run,
                    shell=use_shell,
                    text=True, 
                    encoding='utf-8', 
                    errors='replace'
                )
                
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

#atualizado em 2025/09/20-V49. Arquitetura do 'run' refeita para suportar scripts interativos (input()), herdando os fluxos de I/O do terminal.
@cli.command(context_settings=dict(ignore_unknown_options=True))
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
    cli()