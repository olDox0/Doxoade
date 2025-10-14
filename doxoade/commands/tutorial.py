# doxoade/commands/tutorial.py
#import sys
import click
import os
import shlex
import subprocess
import tempfile

from colorama import Fore, Style
from pathlib import Path

from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.group('tutorial')
def tutorial_group():
    """Comandos para aprender o workflow do doxoade."""
    pass

def _find_project_root():
    current_path = Path(__file__).parent
    while current_path != current_path.parent: # Para evitar loop infinito na raiz do sistema
        if (current_path / "run_doxoade.py").exists():
            return current_path
        current_path = current_path.parent
    return None

@tutorial_group.command('main')
@click.pass_context
def tutorial(ctx):
    """Exibe um guia passo a passo do workflow completo do doxoade."""
    with ExecutionLogger('tutorial-main', '.', ctx.params):
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Guia Completo do Workflow Doxoade ---")
        click.echo(Fore.WHITE + "Este guia mostra os dois principais workflows da doxoade.")

        # --- SEÇÃO A: PROJETOS NOVOS ---
        click.echo(Fore.MAGENTA + Style.BRIGHT + "\n\n--- Workflow A: Iniciando um Projeto NOVO do Zero ---")
        click.echo(Fore.WHITE + "Use este workflow para criar projetos saudáveis desde o primeiro dia.")
        
        click.echo(Fore.YELLOW + "\n--- A.1: Crie e Publique seu Projeto ---")
        click.echo(Fore.GREEN + "   1. Use 'doxoade init' para criar a estrutura local.")
        click.echo(Fore.CYAN + '        $ doxoade init meu-novo-projeto\n')
        click.echo(Fore.GREEN + "   2. Crie um repositório VAZIO no GitHub e copie a URL.")
        click.echo(Fore.GREEN + "   3. Entre no diretório e use 'doxoade git-new' para publicar.")
        click.echo(Fore.CYAN + '        $ cd meu-novo-projeto')
        click.echo(Fore.CYAN + '        $ doxoade git-new "Commit inicial" https://github.com/usuario/repo.git\n')
    
        click.echo(Fore.YELLOW + "\n--- A.2: O Ciclo de Desenvolvimento Diário ---")
        click.echo(Fore.GREEN + "   1. Ative o ambiente virtual. Este é o passo manual mais importante.")
        click.echo(Fore.CYAN + '        $ .\\venv\\Scripts\\activate\n')
        click.echo(Fore.GREEN + "   2. Programe suas alterações...")
        click.echo(Fore.GREEN + "   3. Quando estiver pronto, faça um 'commit seguro' com 'doxoade save'.")
        click.echo(Fore.WHITE + "      (Ele executa 'doxoade check' e aborta o commit se encontrar erros graves)")
        click.echo(Fore.CYAN + '        (venv) > doxoade save "Implementada a classe Usuario"\n')
        click.echo(Fore.GREEN + "   4. Ao final do dia, sincronize seus commits com o remoto usando 'doxoade sync'.")
        click.echo(Fore.CYAN + '        (venv) > doxoade sync')

        # --- SEÇÃO B: PROJETOS EXISTENTES ---
        click.echo(Fore.MAGENTA + Style.BRIGHT + "\n\n--- Workflow B: Diagnosticando e Reparando um Projeto EXISTENTE ---")
        click.echo(Fore.WHITE + "Use este workflow para projetos antigos, clonados ou de terceiros.")

        click.echo(Fore.YELLOW + "\n--- B.1: A Regra de Ouro - Chame o Doutor! ---")
        click.echo(Fore.GREEN + "   1. Navegue para a pasta raiz do projeto que você quer 'curar'.")
        click.echo(Fore.CYAN + '        $ cd C:\\Caminho\\Para\\ProjetoAntigo\n')
        click.echo(Fore.GREEN + "   2. Execute o 'doxoade doctor'. Este é o passo mais poderoso da doxoade.")
        click.echo(Fore.CYAN + '        $ doxoade doctor .\n')
        click.echo(Fore.WHITE + "      O 'doctor' irá automaticamente:")
        click.echo(Fore.WHITE + "        - Verificar se um 'venv' existe e se oferecer para criá-lo.")
        click.echo(Fore.WHITE + "        - Verificar se as dependências do 'requirements.txt' estão instaladas e se oferecer para instalá-las.")
        click.echo(Fore.WHITE + "        - Verificar se o ambiente está isolado e não contaminado.")
        click.echo(Fore.GREEN + "\n   Ao final, o 'doctor' garantirá que o ambiente do projeto está SAUDÁVEL.")

        click.echo(Fore.YELLOW + "\n--- B.2: Inicie o Ciclo de Desenvolvimento ---")
        click.echo(Fore.GREEN + "   Uma vez que o projeto foi 'curado' pelo 'doctor', você pode seguir o ciclo normal:")
        click.echo(Fore.CYAN + '        $ .\\venv\\Scripts\\activate')
        click.echo(Fore.CYAN + '        (venv) > doxoade save "Refatorada a classe legada"')
        click.echo(Fore.CYAN + '        (venv) > doxoade sync')

        click.echo(Fore.YELLOW + Style.BRIGHT + "\n\n--- Fim do Guia ---\n")

@tutorial_group.command('simulation')
@click.pass_context
def tutorial_simulation(ctx):
    """Executa uma simulação guiada do workflow em um ambiente seguro."""
    with ExecutionLogger('tutorial-simulation', '.', ctx.params):
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Bem-vindo à Simulação do Doxoade ---")
        if not click.confirm(Fore.YELLOW + "Podemos começar?"):
            return
        
        # A linha que estava faltando
        project_root = _find_project_root()
        if not project_root:
            click.echo(Fore.RED + "[ERRO] Não foi possível localizar a raiz do projeto doxoade.")
            return
        runner_path = str(project_root / "doxoade.bat")
        
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                sim_project_path = os.path.join(temp_dir, 'meu-projeto-simulado')
                fake_remote_path_str = os.path.join(temp_dir, 'fake_remote.git')
                fake_remote_url = Path(fake_remote_path_str).as_uri()
    
                click.echo(Fore.MAGENTA + f"\n[SIMULAÇÃO] Sandbox criado em: {temp_dir}")
                subprocess.run(['git', 'init', '--bare', fake_remote_path_str], capture_output=True, check=True)
                
                os.chdir(temp_dir)
                _run_sim_command('doxoade init meu-projeto-simulado', runner_path)
    
                os.chdir(sim_project_path)
                _run_sim_command(f'doxoade git-new "Commit inicial simulado" "{fake_remote_url}"', runner_path)
                click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Simulação Concluída com Sucesso! ---")
            finally:
                os.chdir(original_dir)
                click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Fim da Simulação ---")

@tutorial_group.command('interactive')
@click.pass_context
def tutorial_interactive(ctx):
    """Executa uma simulação PRÁTICA onde VOCÊ digita os comandos."""
    with ExecutionLogger('tutorial-interactive', '.', ctx.params):
        click.echo(Fore.CYAN + Style.BRIGHT + "--- Bem-vindo ao Laboratório Prático Doxoade ---")
        if not click.confirm(Fore.YELLOW + "Podemos começar?"):
            return

        project_root = _find_project_root()
        if not project_root:
            click.echo(Fore.RED + "[ERRO] Não foi possível localizar a raiz do projeto doxoade.")
            return
        runner_path = str(project_root / "doxoade.bat")
        
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                sim_project_path = os.path.join(temp_dir, 'meu-projeto-pratico')
                fake_remote_path_str = os.path.join(temp_dir, 'fake_remote.git')
                fake_remote_url = Path(fake_remote_path_str).as_uri()
    
                click.echo(Fore.MAGENTA + f"\n[SIMULAÇÃO] Sandbox criado em: {temp_dir}")
                subprocess.run(['git', 'init', '--bare', fake_remote_path_str], capture_output=True, check=True)
                os.chdir(temp_dir)
    
                if not _prompt_and_run_sim_command(
                    "Primeiro, crie um projeto chamado 'meu-projeto-pratico'",
                    "doxoade init meu-projeto-pratico",
                    runner_path
                ): return
                
                os.chdir(sim_project_path)
                if not _prompt_and_run_sim_command(
                    f"Agora, publique no 'remote' falso com a mensagem 'Meu primeiro commit'.\nURL: {fake_remote_url}",
                    f'doxoade git-new "Meu primeiro commit" "{fake_remote_url}"',
                    runner_path
                ): return
                
                click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Laboratório Concluído com Sucesso! ---")
            finally:
                os.chdir(original_dir)
                click.echo(Fore.MAGENTA + "[SIMULAÇÃO] Sandbox destruído.")

def _run_sim_command(command_str, runner_path):
    """Função auxiliar para exibir, pausar e executar um comando na simulação."""
    click.echo(Fore.GREEN + "\nExecutando o comando:")
    click.echo(Fore.CYAN + f'    $ {command_str}')
    click.pause()
    click.echo(Fore.WHITE + Style.DIM + "--- Saída do Comando ---")
    
    args = shlex.split(command_str)
    # A lógica corrigida: usa o caminho absoluto do runner
    command_to_run = [runner_path] + args[1:]
    
    process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    process.wait()
    click.echo(Fore.WHITE + Style.DIM + "--- Fim da Saída ---\n")

def _prompt_and_run_sim_command(prompt, expected_command, runner_path):
    """Pede ao usuário para digitar um comando, valida, e então o executa."""
    click.echo(Fore.GREEN + f"\nOBJETIVO: {prompt}")
    
    while True:
        user_input = click.prompt(Fore.CYAN + "$")
        if user_input.lower() in ['sair', 'exit']:
            click.echo(Fore.YELLOW + "Simulação encerrada."); return False
        if user_input.lower() in ['ajuda', 'hint', 'help']:
            click.echo(Fore.YELLOW + f"O comando correto é: {expected_command}"); continue

        # Lógica de validação simplificada
        if user_input.strip() == expected_command.strip():
            click.echo(Fore.GREEN + "Correto!"); break
        else:
            click.echo(Fore.RED + "Comando incorreto. Tente novamente.");

    click.echo(Fore.WHITE + Style.DIM + "--- Saída do Comando ---")
    
    # Usamos shlex.split para lidar com as aspas corretamente
    args = shlex.split(user_input)
    command_to_run = [runner_path] + args[1:]
    
    process = subprocess.Popen(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    process.wait()
    click.echo(Fore.WHITE + Style.DIM + "--- Fim da Saída ---")
    return True