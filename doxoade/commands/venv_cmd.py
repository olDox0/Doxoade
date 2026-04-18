# doxoade/doxoade/commands/venv_cmd.py
import os
import click
import ctypes
from doxoade.tools.filesystem import _get_venv_python_executable

@click.command('venv')
@click.option('--admin', is_flag=True, help='Abrir com privilégios de Administrador')
@click.option('--title', help='Título customizado para a janela do terminal')
def venv_cmd(admin, title):
    """Ativa o VENV do projeto garantindo o diretório correto (PASC-8.4)."""
    venv_python = _get_venv_python_executable()
    if not venv_python:
        click.secho(" [!] Venv não localizado na raiz do projeto.", fg='red')
        return

    # Normaliza o diretório atual para evitar problemas com barras
    current_dir = os.path.normpath(os.getcwd())
    activate_path = os.path.normpath(os.path.join(os.path.dirname(venv_python), "activate.bat"))
    
    window_title = title or f"DOXOADE_VENV_{os.path.basename(current_dir)}"
    
    if os.name == 'nt':
        # O SEGREDO: Injetamos 'cd /d "{current_dir}"' no início da cadeia de comandos
        # O uso de aspas triplas ou f-string com aspas duplas protege caminhos com espaços
        cmd_chain = f'cd /d "{current_dir}" && title {window_title} && "{activate_path}"'
        
        # /k executa o comando e mantém o terminal aberto
        cmd_args = f'/k "{cmd_chain}"'
        
        if admin:
            click.echo(f"[*] Elevando privilégios em: {current_dir}")
            # ShellExecuteW: O 4º parâmetro (lpParameters) leva o comando
            # O 5º parâmetro (lpDirectory) é o diretório de trabalho inicial
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                "cmd.exe", 
                cmd_args, 
                current_dir, # Define o diretório de execução
                1
            )
        else:
            # Para o modo não-admin, o 'start' do Windows costuma respeitar o cwd
            os.system(f'start cmd.exe {cmd_args}')