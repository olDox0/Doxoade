# doxoade/doxoade/commands/sandbox.py
import click
import subprocess
import os
import sys
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

@click.command('sandbox')
@click.argument('cmd_to_run')
@click.option('--image', default='python:3.12-alpine', help='Imagem base para o teste.')
@click.option('--install', '-i', is_flag=True, help='Instala requirements.txt antes de rodar.')
@click.option('--vulcan', '-v', is_flag=True, help='Inclui ferramentas de compilação (gcc, musl-dev).')
def sandbox(cmd_to_run, image, install, vulcan):
    """🛡️  Execução Blindada: Roda comandos em um container Docker isolado."""
    
    project_root = _find_project_root(os.getcwd())
    project_name = os.path.basename(project_root)
    
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [AEGIS SANDBOX] Iniciando Ambiente Isolado ---{Style.RESET_ALL}")
    
    # 1. Verifica se o Docker está acessível
    try:
        subprocess.run(['docker', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo(f"{Fore.RED}[ERRO] Docker não encontrado. Certifique-se que o Docker Desktop ou Engine está ativo no WSL.{Style.RESET_ALL}")
        return

    # 2. Constrói o comando de preparação (instalação de dependências)
    setup_cmds = []
    if vulcan:
        click.echo(f"{Fore.YELLOW}   > Preparando toolkit de metalurgia (GCC/Build-base)...{Style.RESET_ALL}")
        setup_cmds.append("apk add --no-cache gcc musl-dev linux-headers")
    
    if install and os.path.exists(os.path.join(project_root, "requirements.txt")):
        click.echo(f"{Fore.YELLOW}   > Sincronizando dependências no container...{Style.RESET_ALL}")
        setup_cmds.append("pip install --no-cache-dir -r requirements.txt")

    # Une os comandos de setup com o comando final
    final_shell_cmd = " && ".join(setup_cmds + [cmd_to_run])
    
    # 3. Mapeamento de Volumes
    # No WSL, o caminho deve ser convertido se estiver no /mnt/c/...
    workdir = "/app"
    
    docker_args = [
        "docker", "run", "--rm",
        "-v", f"{project_root}:{workdir}",
        "-w", workdir,
        image,
        "sh", "-c", final_shell_cmd
    ]

    click.echo(f"{Fore.GREEN}🚀 Executando no container ({image})...{Style.RESET_ALL}")
    click.echo(f"{Style.DIM}------------------------------------------------------------{Style.RESET_ALL}")

    # 4. Execução
    try:
        # Usamos check=False porque queremos capturar o erro do comando interno, não do docker
        result = subprocess.run(docker_args, text=True)
        
        click.echo(f"{Style.DIM}------------------------------------------------------------{Style.RESET_ALL}")
        
        if result.returncode == 0:
            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ TESTE PASSOU: O sistema sobreviveu ao isolamento.{Style.RESET_ALL}")
        else:
            click.echo(f"{Fore.RED}{Style.BRIGHT}✘ TESTE FALHOU: Erros detectados no ambiente limpo (Exit {result.returncode}).{Style.RESET_ALL}")
            sys.exit(result.returncode)

    except Exception as e:
        click.echo(f"{Fore.RED}[SANDBOX CRASH] Falha ao orquestrar container: {e}{Style.RESET_ALL}")