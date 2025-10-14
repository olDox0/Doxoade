# doxoade/commands/run.py
import os
import sys
import subprocess
import json
import time
import threading
from queue import Queue, Empty
from datetime import datetime
from pathlib import Path

import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _get_venv_python_executable
)

__version__ = "34.0 Alfa"

@click.command('run', context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument('script_and_args', nargs=-1, type=click.UNPROCESSED)
@click.option('--trace', is_flag=True, help="Grava a sessão de I/O completa em um arquivo .trace.")
def run(ctx, script_and_args, trace):
    """Executa um script Python, suportando interatividade e gravação de sessão."""
    arguments = ctx.params

    if not script_and_args:
        click.echo(Fore.RED + "[ERRO] Nenhum script especificado.", err=True)
        sys.exit(1)
    
    script_name = script_and_args[0]
    
    with ExecutionLogger('run', '.', arguments) as logger:
        if not os.path.exists(script_name):
            msg = f"Script não encontrado: '{script_name}'."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
            
        python_executable = _get_venv_python_executable()
        if not python_executable:
            msg = "Ambiente virtual 'venv' não encontrado."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
            
        if trace:
            doxoade_dir = os.path.dirname(os.path.abspath(__file__))
            tracer_path = os.path.join(doxoade_dir, '..', 'tracer.py') # Ajuste do caminho

            if not os.path.exists(tracer_path):
                logger.add_finding('error', "Módulo 'tracer.py' não encontrado na instalação da doxoade.")
                click.echo(Fore.RED + "[ERRO] Falha crítica: 'tracer.py' não encontrado.")
                sys.exit(1)
            command_to_run = [python_executable, '-u', tracer_path] + list(script_and_args)
        else:
            command_to_run = [python_executable, '-u'] + list(script_and_args)
        
        click.echo(Fore.CYAN + f"-> Executando '{' '.join(script_and_args)}' com o interpretador do venv...")
        if trace:
            click.echo(Fore.YELLOW + Style.BRIGHT + "   [MODO TRACE ATIVADO] A sessão será gravada.")
        click.echo("-" * 40)
        
        return_code = 1
        if trace:
            if os.name == 'nt':
                return_code = _run_traced_session_windows(command_to_run, logger)
            else:
                logger.add_finding('warning', "O modo --trace ainda não está implementado para plataformas não-Windows.")
                click.echo(Fore.YELLOW + "AVISO: --trace ainda não suportado neste SO. Executando em modo normal.")
                process = subprocess.Popen(command_to_run)
                process.wait()
                return_code = process.returncode
        else:
            try:
                process = subprocess.Popen(command_to_run)
                process.wait()
                return_code = process.returncode
            except KeyboardInterrupt:
                click.echo("\n" + Fore.YELLOW + "[RUN] Interrupção (CTRL+C).")
                return_code = 130
        
        click.echo("-" * 40)
        if return_code != 0:
            logger.add_finding('error', f"O script terminou com o código de erro {return_code}.")
            click.echo(Fore.RED + f"[ERRO] O script '{script_name}' terminou com o código de erro {return_code}.")
            sys.exit(1)
        else:
            click.echo(Fore.GREEN + f"[OK] Script '{script_name}' finalizado com sucesso.")

def _run_traced_session_windows(command, logger):
    """Executa um comando no Windows, gravando stdin, stdout e stderr."""
    trace_dir = Path.home() / '.doxoade' / 'traces'
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file_path = trace_dir / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )
        
        q_out = Queue()
        q_err = Queue()

        def _reader_thread(pipe, queue):
            try:
                for line in iter(pipe.readline, ''):
                    queue.put(line)
            finally:
                pipe.close()
        
        def _writer_thread(pipe, trace_f):
            try:
                for line in sys.stdin:
                    pipe.write(line)
                    pipe.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdin', 'data': line}
                    trace_f.write(json.dumps(log_entry) + '\n')
            except (IOError, OSError):
                pass

        threading.Thread(target=_reader_thread, args=[process.stdout, q_out], daemon=True).start()
        threading.Thread(target=_reader_thread, args=[process.stderr, q_err], daemon=True).start()
        
        with open(trace_file_path, 'w', encoding='utf-8') as trace_file:
            click.echo(Fore.YELLOW + f"   [TRACE] Gravando sessão em '{trace_file_path}'...")
            
            threading.Thread(target=_writer_thread, args=[process.stdin, trace_file], daemon=True).start()

            while process.poll() is None:
                try:
                    line_out = q_out.get_nowait()
                    sys.stdout.write(line_out); sys.stdout.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdout', 'data': line_out}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                try:
                    line_err = q_err.get_nowait()
                    sys.stderr.write(Fore.RED + line_err); sys.stderr.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stderr', 'data': line_err}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                time.sleep(0.05)

            while not q_out.empty() or not q_err.empty():
                try:
                    line_out = q_out.get_nowait()
                    sys.stdout.write(line_out); sys.stdout.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stdout', 'data': line_out}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass
                try:
                    line_err = q_err.get_nowait()
                    sys.stderr.write(Fore.RED + line_err); sys.stderr.flush()
                    log_entry = {'ts': time.time(), 'stream': 'stderr', 'data': line_err}
                    trace_file.write(json.dumps(log_entry) + '\n')
                except Empty: pass

        logger.add_finding('info', f"Sessão gravada com sucesso em '{trace_file_path}'.")
        return process.returncode

    except Exception as e:
        logger.add_finding('error', f"Falha na execução do trace: {e}")
        return 1