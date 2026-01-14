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
# [DOX-UNUSED] from pathlib import Path
from colorama import Fore
from ..shared_tools import (
#      ExecutionLogger, 
      _get_venv_python_executable, 
#      _mine_traceback, 
#      _analyze_runtime_error
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
        f_hash = hashlib.sha256(unique_str.encode('utf-8')).hexdigest()
        
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
    """Retorna o caminho absoluto para a sonda de fluxo."""
    # Assume que a sonda está em doxoade/probes/flow_runner.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Sobe commands -> doxoade
    root = os.path.dirname(current_dir)
    return os.path.join(root, 'probes', 'flow_runner.py')

def _get_probe_path(probe_name: str) -> str:
    """Localiza o script da sonda de forma robusta."""
    from importlib import resources
    try:
        if hasattr(resources, 'files'):
            return str(resources.files('doxoade.probes').joinpath(probe_name))
        with resources.path('doxoade.probes', probe_name) as p:
            return str(p)
    except (ImportError, AttributeError, FileNotFoundError):
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

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

def _smart_find_script(name):
    """(Legado) Tenta encontrar o script python recursivamente."""
    if os.path.exists(name): return name
    for root, dirs, files in os.walk('.'):
        if name in files:
            return os.path.join(root, name)
    return name

#    """Tenta encontrar o script python recursivamente se não estiver no root."""
#    if os.path.exists(name): return name
#    # Procura apenas um nível de profundidade para não demorar
#    for root, dirs, files in os.walk('.'):
#        if name in files:
#            return os.path.join(root, name)
#        # Evita descer em pastas pesadas
#        if 'venv' in dirs: dirs.remove('venv')
#        if '.git' in dirs: dirs.remove('.git')
#    return name

@click.command('run', context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option('--flow', is_flag=True, help="Ativa visualização de execução (Matrix Mode) - Apenas Python.")
@click.option('--internal', is_flag=True, help="Executa comandos internos do Doxoade (Self-Debug).")
@click.argument('target', required=False)
@click.pass_context
def run(ctx, flow, internal, target):
    """
    Executor Universal com Telemetria (MaxTelemetry).
    
    Modos:
    1. Python: 'doxoade run app.py' (Usa venv, suporta --flow)
    2. Interno: 'doxoade run --internal check' (Debug do próprio Doxoade)
    3. Sistema: 'doxoade run npm start' (Executa binários externos)
    """
    # Captura argumentos extras passados após o comando
    extra_args = ctx.args

    if not target and not internal:
        click.echo(Fore.YELLOW + "Uso: doxoade run <script.py | comando> [argumentos]")
        return

    # 1. Configuração do Ambiente (Python)
    env = os.environ.copy()
    current_cwd = os.getcwd()
    
    # Tenta achar venv local explicitamente
    local_venv_exe = os.path.join(current_cwd, 'venv', 'Scripts', 'python.exe')
    if sys.platform != "win32":
        local_venv_exe = os.path.join(current_cwd, 'venv', 'bin', 'python')

    if os.path.exists(local_venv_exe):
        python_exe = local_venv_exe
    else:
        python_exe = _get_venv_python_executable() or sys.executable

    # Configura PYTHONPATH para garantir imports corretos
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{current_cwd}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = current_cwd
    
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = []

    # --- CENÁRIO A: COMANDO INTERNO (--internal) ---
    if internal:
        if not target:
             click.echo(Fore.RED + "Erro: Para --internal, informe o nome do comando (ex: check).")
             return
        
        click.echo(Fore.CYAN + f"--- [RUN:INTERNAL] Debugando 'doxoade {target}' ---")
        
        module_name = f"doxoade.commands.{target.replace('.py', '')}"
        
        if flow:
             # Flow precisa do arquivo físico para instrumentar
             # Tenta localizar o arquivo do comando
             base_dir = os.path.dirname(os.path.abspath(__file__))
             target_script = os.path.join(base_dir, f"{target}.py")
             
             if not os.path.exists(target_script):
                 click.echo(Fore.RED + f"Erro: Arquivo interno '{target_script}' não encontrado.")
                 return
             
             probe = _get_flow_probe_path()
             cmd = [python_exe, probe, target_script] + extra_args
        else:
             # Execução normal via módulo (-m)
             cmd = [python_exe, "-m", module_name] + extra_args

    # --- CENÁRIO B: SCRIPT PYTHON ---
    # Detecta se é Python (.py ou arquivo existente com shebang/extensão)
    elif target.endswith('.py') or (os.path.exists(_smart_find_script(target)) and _smart_find_script(target).endswith('.py')):
        
        real_script = _smart_find_script(target)
        if not os.path.exists(real_script):
            click.echo(Fore.RED + f"Erro: Arquivo Python '{target}' não encontrado.")
            return

        click.echo(Fore.CYAN + f"--- [RUN:PYTHON] Executando: {real_script} ---")

        if flow:
            probe = _get_flow_probe_path()
            cmd = [python_exe, probe, real_script] + extra_args
        else:
            cmd = [python_exe, real_script] + extra_args

    # --- CENÁRIO C: COMANDO DO SISTEMA (Substitui 'exec') ---
    else:
        if flow:
            click.echo(Fore.YELLOW + "[AVISO] --flow não suportado para comandos do sistema. Executando normal.")

        # Reconstrói o comando completo
        full_cmd = [target] + extra_args
        click.echo(Fore.CYAN + f"--- [RUN:SYSTEM] Executando: {' '.join(full_cmd)} ---")

        # Lógica de Shell para Windows (comandos internos como dir, echo)
        use_shell = False
        if os.name == 'nt':
            # Lista de comandos que exigem shell=True no Windows
            win_shell_cmds = {'dir', 'echo', 'type', 'del', 'copy', 'move', 'cls', 'mkdir', 'rmdir'}
            if target.lower() in win_shell_cmds:
                use_shell = True
        
        # Executa diretamente
        try:
            # O MaxTelemetry (Chronos) monitorará os recursos deste subprocesso
            subprocess.run(full_cmd, env=env, check=True, shell=use_shell)
            return # Sai com sucesso
        except FileNotFoundError:
            click.echo(Fore.RED + f"[ERRO] Comando não encontrado: {target}")
            click.echo(Fore.YELLOW + "Dica: Se for um script Python, adicione a extensão .py")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            click.echo(Fore.RED + f"\n[FALHA] Comando retornou código {e.returncode}.")
            sys.exit(e.returncode)
        except KeyboardInterrupt:
            click.echo(Fore.YELLOW + "\n[INTERROMPIDO] Execução cancelada.")
            return

    # Execução para Casos A (Internal) e B (Python)
    try:
        # shell=False é mais seguro para Python
        subprocess.run(cmd, env=env, check=True, shell=False)
        
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
    ctx.invoke(run, target=script, flow=True, internal=False)
