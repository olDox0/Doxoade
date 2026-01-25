# -*- coding: utf-8 -*-
"""
Debug Suite - Chief Gold Orchestrator.
Compliance: MPoT-1, PASC-1.
"""
import click
import subprocess
import sys
import json
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
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
        parts = res.stdout.split("---DOXOADE-DEBUG-DATA---")
        
        if len(parts) < 2:
            click.secho("\n[!] Sonda falhou ao retornar dados estruturados.", fg='red')
            if res.stderr: click.echo(res.stderr)
            return

        data = json.loads(parts[1])
        if data.get('status') == 'error':
            report_crash(data, script)
        else:
            click.secho("\n✅ [ SUCESSO ] Execução concluída.", fg='green')
            render_variable_table(data.get('variables'))
            
    except Exception as e:
        # PASC-5.3: Tratamento informativo
        click.secho(f"\n❌ Falha Crítica no Orquestrador: {e}", fg='red', bold=True)