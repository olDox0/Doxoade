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

@click.command('run')
@click.argument('script', required=False)
@click.argument('args', nargs=-1)
@click.option('--flow', is_flag=True, help="Ativa visualização de execução (Matrix Mode).")
@click.option('--internal', is_flag=True, help="Executa comandos internos do Doxoade (Self-Debug).")
@click.pass_context
def run(ctx, script, args, flow, internal):
    """
    Executa um script Python ou comando interno no ambiente controlado.
    
    Exemplos:
        doxoade run main.py
        doxoade run main --flow
        doxoade run check . --internal
    """
    # 1. Configuração do Ambiente
    python_exe = _get_venv_python_executable()
    if not python_exe:
        # Fallback para o python do sistema se não houver venv, mas avisa
        python_exe = sys.executable
        if not internal:
            click.echo(Fore.YELLOW + "[AVISO] 'venv' não detectado. Usando Python do sistema.")

    # 2. Resolução do Alvo
    if internal:
        # Modo interno: roda o próprio doxoade como módulo
#        target_script = "-m"
        target_args = ["doxoade", script] + list(args) if script else ["doxoade"] + list(args)
        
        # Ajuste para chamar o módulo
        cmd = [python_exe] + target_args
        display_name = f"doxoade (internal) {' '.join(target_args)}"
    
    else:
        # Modo Script de Usuário
        if not script:
            click.echo(Fore.RED + "Erro: Argumento SCRIPT necessário (ou use --internal).")
            return

        resolved_script = _smart_find_script(script)
        if not os.path.exists(resolved_script):
            click.echo(Fore.RED + f"Erro: Arquivo '{resolved_script}' não encontrado.")
            return

        cmd = _build_execution_command(resolved_script, python_exe, flow, list(args))
        display_name = resolved_script

    # 3. Execução
    click.echo(Fore.CYAN + f"--- [RUN] Executando: {display_name} ---")
    
    try:
        # Usamos capture_output=True se precisarmos analisar o erro (Antifragilidade)
        # Mas para interatividade (input/output em tempo real), normalmente não capturamos.
        # Dilema: Se capturarmos, perdemos interatividade. Se não capturarmos, perdemos o erro para o Gênese.
        # Solução V9: Em modo normal, deixamos fluir. Se quebrar, o usuário vê no terminal.
        # Se for FLOW, capturamos para análise.
        
        if flow:
            # Modo Flow captura tudo para processar
            result = subprocess.run(cmd, text=True, capture_output=True, encoding='utf-8', errors='replace')
            print(result.stdout) # Imprime o output do flow
            print(result.stderr, file=sys.stderr)
            return_code = result.returncode
            stderr_content = result.stderr
        else:
            # Modo Interativo (Normal) - Permite input() do usuário
            # Não capturamos stderr aqui, então a Gênese de runtime fica limitada neste modo
            # para preservar a UX.
            result = subprocess.run(cmd)
            return_code = result.returncode
            stderr_content = None # Não disponível em modo stream

        # 4. Pós-Processamento e Aprendizado (Antifragilidade)
        if return_code != 0:
            click.echo(Fore.RED + f"\n[FALHA] Processo terminou com código {return_code}.")
            
            if stderr_content:
                # Gênese V4: Mineração de Traceback
                error_data = _mine_traceback(stderr_content)
                if error_data:
                    suggestion = _analyze_runtime_error(error_data)
                    
                    click.echo(Fore.YELLOW + "\n--- [DIAGNÓSTICO RUNTIME] ---")
                    click.echo(f"Erro: {error_data['error_type']}")
                    click.echo(f"Msg : {error_data['message']}")
                    click.echo(f"Loc : {error_data['file']}:{error_data['line']}")
                    
                    if suggestion:
                        click.echo(Fore.GREEN + f"Sugestão: {suggestion}")
                    
                    # Gênese V9: Registro
                    _register_runtime_incident(error_data)
                    click.echo(Fore.CYAN + "   > [GÊNESE] Incidente registrado para aprendizado.")

    except KeyboardInterrupt:
        click.echo(Fore.YELLOW + "\n[RUN] Interrompido pelo usuário.")
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO SISTEMA] Falha ao invocar subprocesso: {e}")