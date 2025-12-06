# doxoade/commands/run.py
"""
Módulo executor do Doxoade.
Responsável por rodar scripts Python dentro do ambiente virtual gerenciado,
com suporte a instrumentação (Flow), execução interna e captura de falhas para o Gênese.
"""
import click
import subprocess
import sys
import os
#import shlex
from colorama import Fore
from ..shared_tools import (
    #ExecutionLogger, 
    _get_venv_python_executable, 
    _mine_traceback, 
    _analyze_runtime_error
)
from ..database import get_db_connection
from datetime import datetime, timezone

def _register_runtime_incident(error_data):
    """
    (Gênese V9) Registra um erro de runtime no banco de dados para aprendizado futuro.
    
    Args:
        error_data (dict): Dicionário contendo 'message', 'file', 'line', etc.
    """
    if not error_data: return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Gera um hash único para o erro
        import hashlib
        unique_str = f"{error_data.get('file')}:{error_data.get('line')}:{error_data.get('message')}"
        f_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        
        # Define categoria baseada no tipo de erro
        category = "RUNTIME-CRASH"
        
        cursor.execute("""
            INSERT OR REPLACE INTO open_incidents 
            (finding_hash, file_path, line, message, category, commit_hash, timestamp, project_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f_hash,
            error_data.get('file'),
            error_data.get('line', 0),
            error_data.get('message'),
            category,
            "runtime", # Não associado a commit específico
            datetime.now(timezone.utc).isoformat(),
            os.getcwd()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        click.echo(Fore.RED + f"[GÊNESE ERROR] Falha ao registrar incidente: {e}")

def _get_flow_probe_path():
    """Retorna o caminho absoluto para a sonda 'flow_runner.py'."""
    # [MPoT-5] Contrato: O arquivo deve existir.
    from importlib import resources
    try:
        with resources.path('doxoade.probes', 'flow_runner.py') as p:
            path = str(p)
    except (ImportError, AttributeError):
        # Fallback para sistemas antigos
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'probes', 'flow_runner.py')
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Sonda Flow não encontrada em: {path}")
    return path

def _smart_find_script(script_name):
    """
    Tenta localizar o script alvo, permitindo omissão de extensão .py.
    
    Args:
        script_name (str): Nome ou caminho do script.
    
    Returns:
        str: Caminho resolvido ou o original se não encontrado.
    """
    if os.path.exists(script_name):
        return script_name
    
    if not script_name.endswith('.py'):
        potential = script_name + ".py"
        if os.path.exists(potential):
            return potential
            
    # [MPoT-5] Contrato implícito: Retorna o original para o subprocesso falhar ruidosamente depois
    return script_name

def _build_execution_command(script_path, python_exe, flow=False, args=None):
    """
    Constrói a lista de argumentos para o subprocesso.
    Separa a lógica de montagem da lógica de execução (facilita teste unitário).
    """
    cmd = [python_exe]
    
    if flow:
        # Modo Matrix: Injeta o flow_runner antes do script
        probe = _get_flow_probe_path()
        cmd.append(probe)
        
    cmd.append(script_path)
    
    if args:
        cmd.extend(args)
        
    return cmd

@click.command('run', context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option('--flow', is_flag=True, help="Ativa visualização de execução (Matrix Mode).")
@click.option('--internal', is_flag=True, help="Executa comandos internos do Doxoade (Self-Debug).")
@click.argument('script', required=False)
@click.pass_context
def run(ctx, flow, internal, script):
    """
    Executa um script Python com ambiente controlado.
    
    Exemplos:
        doxoade run main.py
        doxoade run main.py --flow
        doxoade flow main.py
        doxoade run check --internal (Equivale a rodar python -m doxoade.commands.check)
    """
    args = ctx.args  # Argumentos extras passados após o script
    
    if not script and not internal:
        click.echo(Fore.RED + "Erro: Especifique um script ou use --internal.")
        return

    # Configurar Ambiente
    env = os.environ.copy()
    current_cwd = os.getcwd()
    
    # Adiciona o diretório atual ao PYTHONPATH
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{current_cwd}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = current_cwd
    
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = []
    
    if internal:
        if not script:
             click.echo(Fore.RED + "Erro: Para --internal, informe o nome do comando (ex: check).")
             return
        
        # Modo Internal: Roda como módulo (-m) para preservar imports relativos
        # Ex: doxoade run check --internal -> python -m doxoade.commands.check
        module_name = f"doxoade.commands.{script.replace('.py', '')}"
        
        # Para comandos internos funcionarem como __main__, eles precisam ter o bloco if __name__ == "__main__":
        # O check.py atual é desenhado para ser invocado pelo Click, mas podemos forçar a execução.
        # Se usarmos --flow com internal, usamos o flow_runner no arquivo físico.
        
        if flow:
             # Flow precisa do arquivo físico
             target_script = f"doxoade/commands/{script}.py" if not script.endswith(".py") else f"doxoade/commands/{script}"
             if not os.path.exists(target_script):
                 click.echo(Fore.RED + f"Erro: Arquivo interno '{target_script}' não encontrado.")
                 return
             
             # Precisamos achar o flow_runner
             flow_runner_path = os.path.join("doxoade", "probes", "flow_runner.py")
             cmd = [sys.executable, flow_runner_path, target_script] + args
             
        else:
             # Execução normal interna via módulo
             cmd = [sys.executable, "-m", module_name] + args

    else:
        # Modo Script Normal
        target_script = script
        if not os.path.exists(target_script):
            click.echo(Fore.RED + f"Erro: Arquivo '{target_script}' não encontrado.")
            return

        if flow:
            flow_runner_path = os.path.join("doxoade", "probes", "flow_runner.py")
            # Se não achar localmente (instalado via pip?), tenta achar relativo ao pacote
            if not os.path.exists(flow_runner_path):
                 # Fallback: Tenta achar onde o doxoade está instalado
                 import doxoade
                 pkg_dir = os.path.dirname(doxoade.__file__)
                 flow_runner_path = os.path.join(pkg_dir, "probes", "flow_runner.py")
            
            if not os.path.exists(flow_runner_path):
                 click.echo(Fore.RED + "Erro: flow_runner.py não encontrado (instalação corrompida?).")
                 return

            cmd = [sys.executable, flow_runner_path, target_script] + args
        else:
            cmd = [sys.executable, target_script] + args

    try:
        if not flow:
            click.echo(Fore.CYAN + f"--- [RUN] Executando: {' '.join(cmd)} ---")
        
        subprocess.run(cmd, env=env, check=True)
        
    except subprocess.CalledProcessError as e:
        click.echo(Fore.RED + f"\n[FALHA] Processo terminou com código {e.returncode}.")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[INTERROMPIDO] Execução cancelada pelo usuário.")
    except Exception as e:
        click.echo(Fore.RED + f"\n[ERRO INTERNO] {e}")

@click.command('flow', context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.argument('script')
@click.pass_context
def flow_command(ctx, script):
    """Alias para 'doxoade run --flow'."""
    ctx.invoke(run, script=script, flow=True, internal=False)
