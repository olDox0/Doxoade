# -*- coding: utf-8 -*-
"""
Debug Suite - Chief Gold Orchestrator.
Compliance: MPoT-1, PASC-1.
"""
import click
import subprocess
import sys
import json
from doxoade.tools.doxcolors import Fore
from .debug_utils import get_debug_env, build_probe_command
from .debug_io import print_debug_header, render_variable_table, report_crash
from ..shared_tools import _get_venv_python_executable
@click.command('debug')
@click.argument('script', type=click.Path(exists=True))
@click.option('--watch', help='Monitora uma variável em tempo real.')
@click.option('--bottleneck', '-b', is_flag=True, help='Exibe apenas linhas lentas.')
@click.option('--threshold', '-t', type=int, default=100)
@click.option('--args', help='Args do script.')
def debug(script, watch, bottleneck, threshold, args):
    """🩺 Autópsia Forense ou Monitoramento (MPoT-5)."""
    python_exe = _get_venv_python_executable() or sys.executable
    env = get_debug_env(script)
    
    # --- MODO LIVE (Flow Runner) ---
    if watch or bottleneck:
        from ..probes import flow_runner
        print_debug_header(script, "VIGILÂNCIA" if watch else "GARGALOS")
        cmd = build_probe_command(python_exe, flow_runner.__file__, script, 
                                  watch=watch, bottleneck=bottleneck, threshold=threshold, args=args)
        try:
            subprocess.run(cmd, env=env, shell=False)
        except KeyboardInterrupt:
            click.echo(f"\n{click.style('[!]', fg='yellow')} Monitoramento encerrado.")
        return
    # --- MODO AUTÓPSIA (Debug Probe) ---
    from ..probes import debug_probe
    print_debug_header(script)
    cmd = build_probe_command(python_exe, debug_probe.__file__, script, args=args)
    try:
        # Mudamos de .run (que espera o fim) para .Popen (que monitora em tempo real)
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            encoding='utf-8', 
            env=env
        )
        
        click.echo(Fore.YELLOW + "   > Aguardando sinalização da sonda...")
        
        # [TECNOLOGIA NEXUS] Tenta ler a primeira saída para ver se o boot falhou
        try:
            # Aguarda um tempo curto para ver se o servidor crashou no boot
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            import sys as exc_sys
            import os as exc_os
            exc_type, exc_obj, exc_tb = exc_sys.exc_info()
            fname = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f"\033[0m \033[1m \nFilename: {fname}   \n■ Line: {line_number} \033[31m \n■ Exception type: {exc_type} \n■ Exception value: {'\n  >>>  '.join(str(exc_obj).split('\''))} \033[0m")
#            print(f"\033[0m \033[1m \nFilename: {fname}   \n■ Line: {line_number} \033[31m \n■ Exception type: {exc_type} \n■ Exception value: {exc_obj} \033[0m")
            
            # Se deu timeout, o servidor está VIVO e em loop (Comportamento esperado do FastAPI)
            click.secho("\n📡 [ SERVIDOR ATIVO ] Loop detectado. O rastro está em background.", fg='cyan')
            click.echo(Fore.WHITE + "   > Para servidores, use 'doxoade run --flow' para ver as rotas em real-time.")
            return
        # Se o processo terminou em menos de 5s, houve um erro ou o script era curto
        if "---DOXOADE-DEBUG-DATA---" in stdout:
            parts = stdout.split("---DOXOADE-DEBUG-DATA---")
            data = json.loads(parts[1])
            if data.get('status') == 'error':
                report_crash(data, script)
            else:
                click.secho("\n✅ [ SUCESSO ] Execução concluída.", fg='green')
                render_variable_table(data.get('variables'))
        else:
            # Se não tem o marcador e o processo morreu, imprimimos o erro real
            click.secho("\n🚨 [ FALHA DE BOOTSTRAP ]", fg='red', bold=True)
            if stderr: click.echo(f"{Fore.RED}{stderr}")
            if stdout: click.echo(stdout)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
        exc_trace(exc_tb)
        click.secho(f"\n❌ Erro no Orquestrador: {e}", fg='red')