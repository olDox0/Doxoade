# doxoade/commands/init.py
import os
import sys
import subprocess
import re

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command
)

#init(autoreset=True)

__version__ = "34.0 Alfa"

@click.command('init')
@click.pass_context
@click.argument('project_name', required=False)
@click.option('--remote', help="URL do repositório Git remoto para publicação automática.")
def init(ctx, project_name, remote):
    """Cria a estrutura de um novo projeto e, opcionalmente, o publica no GitHub."""
    arguments = ctx.params
    path = '.' # O comando 'init' opera a partir do diretório atual

    with ExecutionLogger('init', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [INIT] Assistente de Criação de Novo Projeto ---")
        if not project_name:
            project_name = click.prompt("Qual é o nome do seu novo projeto?")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
            msg = "O nome do projeto deve conter apenas letras, números, hífens e underscores."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
        
        project_path = os.path.abspath(project_name)
        if os.path.exists(project_path):
            msg = f"O diretório '{project_path}' já existe."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
            
        original_dir = os.getcwd()
        
        try:
            # --- LÓGICA DE CRIAÇÃO LOCAL ---
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
                logger.add_finding('error', "Falha ao inicializar o repositório Git.")
                sys.exit(1)

            click.echo(Fore.GREEN + "\n[OK] Estrutura local do projeto criada com sucesso!")

            # --- LÓGICA DE PUBLICAÇÃO AUTOMÁTICA ---
            if remote:
                click.echo(Fore.CYAN + "\n--- Publicando projeto no repositório remoto ---")
                
                click.echo(f"   > Adicionando remote 'origin' -> {remote}")
                if not _run_git_command(['remote', 'add', 'origin', remote]):
                    logger.add_finding('error', "Falha ao adicionar o remote Git.")
                    sys.exit(1)
                
                click.echo("   > Adicionando todos os arquivos ao Git (git add .)...")
                if not _run_git_command(['add', '.']):
                    logger.add_finding('error', "Falha ao executar 'git add .'.")
                    sys.exit(1)

                commit_message = f"Commit inicial: Estrutura do projeto {project_name}"
                click.echo(f"   > Criando commit inicial com a mensagem: '{commit_message}'...")
                if not _run_git_command(['commit', '-m', commit_message]):
                    logger.add_finding('error', "Falha ao executar 'git commit'.")
                    sys.exit(1)

                click.echo("   > Enviando para o branch 'main' no remote 'origin' (git push)...")
                if not _run_git_command(['push', '--set-upstream', 'origin', 'main']):
                    msg = "Falha ao enviar. Verifique a URL, suas permissões e se o repositório remoto está VAZIO."
                    logger.add_finding('error', msg)
                    click.echo(Fore.RED + f"[ERRO] {msg}")
                    sys.exit(1)

                click.echo(Fore.GREEN + "\n[OK] Projeto publicado com sucesso!")
                click.echo(f"   > Veja seu repositório em: {remote}")
            
            else:
                click.echo(Fore.YELLOW + "\nLembrete: Este é um projeto local. Para publicá-lo mais tarde, use 'doxoade git-new'.")

        except Exception as e:
            logger.add_finding('fatal_error', f"Ocorreu um erro inesperado durante a inicialização: {e}")
            click.echo(Fore.RED + f"[ERRO] Ocorreu um erro inesperado: {e}")
        finally:
            os.chdir(original_dir)