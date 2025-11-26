# doxoade/commands/run.py
import click
import subprocess
import sys
import os
# [DOX-UNUSED] import glob 
from colorama import Fore, Style
from ..shared_tools import _get_venv_python_executable, _mine_traceback, _analyze_runtime_error

def _get_flow_probe_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'probes', 'flow_runner.py')

def _get_wrapper_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'probes', 'command_wrapper.py')

def _smart_find_script(script_name, root_path='.'):
    """Procura um script Python recursivamente se não estiver na raiz."""
    if os.path.exists(script_name):
        return script_name
        
    click.echo(Fore.YELLOW + f"   > '{script_name}' não encontrado na raiz. Buscando no projeto...")
    
    matches = []
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in ('venv', '.git', '__pycache__', 'node_modules', '.doxoade_cache')]
        if script_name in files:
            matches.append(os.path.join(root, script_name))
            
    if not matches:
        return None
    
    if len(matches) == 1:
        click.echo(Fore.GREEN + f"   > Encontrado em: {matches[0]}")
        return matches[0]
    else:
        matches.sort(key=len)
        chosen = matches[0]
        click.echo(Fore.YELLOW + f"   > Múltiplos arquivos encontrados. Usando: {chosen}")
        return chosen

@click.command('run')
@click.argument('script', required=False)
@click.argument('args', nargs=-1)
@click.option('--flow', is_flag=True, help="Ativa o modo Flow (Rastreamento visual).")
@click.option('--internal', is_flag=True, help="Executa comando interno do Doxoade.")
@click.pass_context
def run(ctx, script, args, flow, internal):
    """Executa um script Python ou comando interno."""
    
    venv_python = _get_venv_python_executable()
    if not venv_python:
        click.echo(Fore.RED + "[ERRO] Ambiente virtual não encontrado.")
        sys.exit(1)

    # --- CONFIGURAÇÃO DO COMANDO ---
    if internal:
        if not flow:
            click.echo(Fore.YELLOW + "[AVISO] --internal geralmente é usado com --flow. Ativando Flow.")
            flow = True
        wrapper_path = _get_wrapper_path()
        probe_path = _get_flow_probe_path()
        command = [venv_python, probe_path, wrapper_path, script] + list(args)
        click.echo(Fore.MAGENTA + Style.BRIGHT + f"--- [META-FLOW] Analisando comando interno: {script} ---")
        
    else:
        if not script:
            subprocess.run([venv_python]); return

        real_script_path = _smart_find_script(script)
        if not real_script_path:
            click.echo(Fore.RED + f"[ERRO] O arquivo '{script}' não foi encontrado neste projeto.")
            sys.exit(1)

        if flow:
            probe_path = _get_flow_probe_path()
            if not os.path.exists(probe_path):
                 click.echo(Fore.RED + "[ERRO INTERNO] Sonda Flow não encontrada.")
                 sys.exit(1)
            command = [venv_python, probe_path, real_script_path] + list(args)
            click.echo(Fore.MAGENTA + Style.BRIGHT + "--- [ATIVANDO MODO FLOW] ---")
        else:
            command = [venv_python, real_script_path] + list(args)
            click.echo(Fore.CYAN + f"--- [RUN] Executando: {real_script_path} ---")

    # --- EXECUÇÃO BLINDADA ---
    try:
        if flow:
            # MODO FLOW: Captura output para não quebrar layout e permitir análise
            process = subprocess.run(
                command, 
                capture_output=True,
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            
            # Mostra o que foi capturado
            if process.stdout: click.echo(process.stdout, nl=False)
            if process.stderr: click.echo(Fore.RED + process.stderr, nl=False)

            # Análise de Falha (Gênese V4) só funciona se capturamos stderr
            if process.returncode != 0:
                click.echo(Style.BRIGHT + Fore.YELLOW + "\n\n--- [ANÁLISE DE FALHA (Gênese V4)] ---")
                error_data = _mine_traceback(process.stderr)
                
                if error_data:
                    click.echo(Fore.RED + f"Erro Detectado: {error_data['error_type']}")
                    click.echo(Fore.WHITE + f"   > Arquivo: {os.path.basename(error_data['file'])} (Linha {error_data['line']})")
                    click.echo(Fore.WHITE + f"   > Mensagem: {error_data['message']}")
                    
                    if error_data.get('code') and error_data['code'] != 'N/A':
                        click.echo(Fore.YELLOW + f"   > {error_data['code']}")
                    
                    suggestion = _analyze_runtime_error(error_data)
                    if suggestion:
                        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUGESTÃO AUTOMÁTICA]")
                        click.echo(Fore.GREEN + f"   {suggestion}")
                else:
                    click.echo(Fore.YELLOW + "   > Não foi possível estruturar o traceback.")
                sys.exit(process.returncode)

        else:
            # MODO NORMAL: Execução Direta (Interativo)
            # Usa subprocess.call para conectar diretamente ao terminal (input() funciona)
            # Não captura stderr, então Gênese V4 não roda aqui (o usuário vê o erro nativo do Python)
            return_code = subprocess.call(command)
            sys.exit(return_code)

    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[INFO] Execução interrompida pelo usuário.")
    except Exception as e:
        click.echo(Fore.RED + f"\n[ERRO CRÍTICO NO RUNNER] {e}")