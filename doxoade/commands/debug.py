# -*- coding: utf-8 -*-
# doxoade/commands/debug.py
import click
import subprocess
import sys
import os
import json
from colorama import Fore, Style
from ..shared_tools import _get_venv_python_executable, _find_project_root

__all__ = ['debug']

def _render_variable_table(variables: dict):
    if not variables: return
    click.echo(Fore.CYAN + "\n[ ESTADO DAS VARIÁVEIS ]")
    for k, v in variables.items():
        val = str(v).replace('\n', ' ')
        if len(val) > 70: val = val[:67] + "..."
        click.echo(f"   {Fore.BLUE}{k:<18} {Fore.WHITE}│ {Style.DIM}{val}")

@click.command('debug')
@click.argument('script', type=click.Path(exists=True))
@click.option('--watch', help='Monitora uma variável em tempo real.')
@click.option('--bottleneck', '-b', is_flag=True, help='Exibe apenas linhas lentas (Gargalos).')
@click.option('--threshold', '-t', type=int, default=100, help='Limiar em ms (padrão: 100, ouseja 100ms).')
@click.option('--args', help='Args do script (entre aspas).')
def debug(script, watch, bottleneck, threshold, args):
    """🩺 Autópsia Forense ou Monitoramento em Tempo Real."""
    python_exe = _get_venv_python_executable() or sys.executable
    project_root = _find_project_root(os.path.abspath(script))
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(project_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    # --- MODO LIVE (Flow Runner: Watch ou Bottleneck) ---
    if watch or bottleneck:
        from ..probes import flow_runner
        mode_label = "VIGILÂNCIA" if watch else "GARGALOS"
        click.echo(Fore.CYAN + f"🔍 [ {mode_label} ] Iniciando rastro em {script}...")
        
        # Construção dinâmica de argumentos para a sonda
        cmd = [python_exe, flow_runner.__file__, script]
        if watch: cmd.extend(["--watch", watch])
        if bottleneck: cmd.extend(["--slow", str(threshold)])
        if args: cmd.extend(args.split())
        
        try:
            subprocess.run(cmd, env=env, shell=False)
        except KeyboardInterrupt:
            click.echo(f"\n{Fore.YELLOW}[!] Monitoramento encerrado.")
        return

    # --- MODO AUTÓPSIA (Debug Probe: Post-Mortem) ---
    from ..probes import debug_probe
    click.echo(Fore.BLUE + Style.BRIGHT + f"[ DEBUG ] Analisando execução de {Fore.CYAN}{script}...")
    cmd = [python_exe, debug_probe.__file__, script]
    if args: cmd.extend(args.split())

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
        parts = result.stdout.split("---DOXOADE-DEBUG-DATA---")
        if len(parts) < 2:
            click.echo(Fore.RED + "\n[!] Sonda não retornou dados. Verifique erros de sintaxe.")
            if result.stderr: click.echo(result.stderr)
            return

        data = json.loads(parts[1])
        if data['status'] == 'error':
            click.echo(f"\n{Fore.RED}{Style.BRIGHT}🚨 [ CRASH DETECTADO ]")
            click.echo(f"{Fore.RED}Erro: {data['error']}")
            click.echo(f"{Fore.YELLOW}Local: L{data.get('line', '??')} em {os.path.basename(script)}")
            _render_variable_table(data.get('variables'))
            click.echo(Fore.RED + "\n--- TRACEBACK ---")
            click.echo(data.get('traceback'))
        else:
            click.echo(Fore.GREEN + "\n✅ [ SUCESSO ] Execução concluída.")
            _render_variable_table(data.get('variables'))
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha: {e}")