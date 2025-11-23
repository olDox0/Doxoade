# doxoade/commands/run.py
import click
import subprocess
import sys
import os
#import glob 
from colorama import Fore, Style
from ..shared_tools import _get_venv_python_executable, _mine_traceback, _analyze_runtime_error

def _get_flow_probe_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'probes', 'flow_runner.py')

def _smart_find_script(script_name, root_path='.'):
    """Procura um script Python recursivamente se não estiver na raiz."""
    if os.path.exists(script_name):
        return script_name
        
    click.echo(Fore.YELLOW + f"   > '{script_name}' não encontrado na raiz. Buscando no projeto...")
    
    matches = []
    for root, dirs, files in os.walk(root_path):
        # Otimização: Ignora pastas pesadas
        dirs[:] = [d for d in dirs if d not in ('venv', '.git', '__pycache__', 'node_modules', '.doxoade_cache')]
        
        if script_name in files:
            matches.append(os.path.join(root, script_name))
            
    if not matches:
        return None
    
    if len(matches) == 1:
        click.echo(Fore.GREEN + f"   > Encontrado em: {matches[0]}")
        return matches[0]
    else:
        # Se houver vários, usa o mais curto (mais próximo da raiz) ou o primeiro
        matches.sort(key=len)
        chosen = matches[0]
        click.echo(Fore.YELLOW + f"   > Múltiplos arquivos encontrados. Usando: {chosen}")
        return chosen

@click.command('run')
@click.argument('script', required=False)
@click.argument('args', nargs=-1)
@click.option('--flow', is_flag=True, help="Ativa o modo Flow (Rastreamento visual).")
@click.pass_context
def run(ctx, script, args, flow):
    """Executa um script Python. Se não achar, procura no projeto."""
    
    venv_python = _get_venv_python_executable()
    
    if not venv_python:
        click.echo(Fore.RED + "[ERRO] Ambiente virtual não encontrado. Execute 'doxoade doctor' primeiro.")
        sys.exit(1)

    if not script:
        subprocess.run([venv_python])
        return

    # --- CORREÇÃO AQUI: Bloqueio se não encontrar ---
    real_script_path = _smart_find_script(script)
    
    if not real_script_path:
        click.echo(Fore.RED + f"[ERRO] O arquivo '{script}' não foi encontrado neste projeto.")
        # Não tenta rodar, apenas sai
        sys.exit(1)

    # Configuração do Comando
    if flow:
        probe_path = _get_flow_probe_path()
        if not os.path.exists(probe_path):
             click.echo(Fore.RED + f"[ERRO INTERNO] Sonda Flow não encontrada em: {probe_path}")
             sys.exit(1)
             
        command = [venv_python, probe_path, real_script_path] + list(args)
        click.echo(Fore.MAGENTA + Style.BRIGHT + "--- [ATIVANDO MODO FLOW] ---")
    else:
        command = [venv_python, real_script_path] + list(args)
        click.echo(Fore.CYAN + f"--- [RUN] Executando: {real_script_path} ---")
    
    # Execução Blindada
    try:
        # Captura output para análise, mas faz streaming se possível seria ideal. 
        # Como estamos usando capture_output=True, o usuário vê tudo no final ou se der erro.
        # Para o FLOW funcionar bem com input/output em tempo real, o ideal seria não capturar
        # MAS para a nossa Gênese V4 (Análise de Erro) funcionar, precisamos capturar o stderr.
        # Dilema resolvido: O Flow imprime linha a linha, então capture_output segura isso até o fim?
        # Não, no código anterior vimos o Flow saindo. Ah, porque o python bufferiza.
        
        process = subprocess.run(
            command, 
            capture_output=True,
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        
        if process.stdout:
            click.echo(process.stdout, nl=False)
        
        if process.stderr:
            # Se for erro, imprime em vermelho
            click.echo(Fore.RED + process.stderr, nl=False)

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
                click.echo(Fore.YELLOW + "   > Não foi possível estruturar o traceback (erro genérico ou desconhecido).")
                
            sys.exit(process.returncode)

    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[INFO] Execução interrompida pelo usuário.")
    except Exception as e:
        click.echo(Fore.RED + f"\n[ERRO CRÍTICO NO RUNNER] {e}")