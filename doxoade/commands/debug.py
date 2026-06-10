# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/debug.py
"""
Debug Suite v2.1 - Chief Gold Orchestrator.
Compliance: MPoT-1, PASC-1.
"""
import click
import os
import sys
import traceback
from doxoade.rescue import activate_protocol
from doxoade.tools.doxcolors import Fore, Style

@click.command('debug')
@click.argument('script', required=False)
@click.option('--args', 'target_args',
                help="Args do script.")
@click.option('--watch', 
                help="Monitora uma variável em tempo real.")
@click.option('--intern',      '-i',                
                help="Executa e depura um comando interno. Ex: --intern 'check .'")
@click.option('--flow-val', is_flag=True, 
                help="Inspeção de variáveis no rastro.")
@click.option('--flow-import', is_flag=True, 
                help="Rastro de I/O e imports.")
@click.option('--flow-func', is_flag=True, 
                help="Rastro de chamadas de funções.")
@click.option('--bottleneck',  '-b',  is_flag=True, 
                help="Exibe linhas com tempo por linha.")
@click.option('--no-compress', '-nc', is_flag=True, 
                help="Desativa compressão de loops repetidos.")
@click.option('--processing-limiter', '-pl', type=float, 
                help="Limite de CPU %.")
@click.option('--ram-limiter', '-rl', type=str, 
                help="Limite de RAM (ex: 512mb).")
@click.option('--disk-limiter', '-dl', type=str, 
                help="Limite de escrita em disco.")
@click.option('--no-vulcan', is_flag=True, 
                help="Desativa o Turbo Nativo.")
@click.option('--profile',     '-p',  is_flag=True, 
                help="Perfil de CPU (tempo).")
@click.option('--memory',      '-m',  is_flag=True, 
                help="Autópsia profunda de Memória (GC + Tracebacks).")
@click.option('--threshold',   '-t',  type=float, default=0.0, 
                help="Filtra linhas abaixo de N ms.")
@click.option('--sniff',                            
                help="Monitora I/O e Variáveis de um arquivo específico ao vivo.")
@click.option('--audit-rescue', is_flag=True, 
                help="Executa necropsia completa no sistema de resgate.")
@click.option('--meta-analysis', is_flag=True, 
                help="Executa meta diagnostico sob o sistema lazarus.")
@click.option('--status', is_flag=True,
                help="Verifica a saúde operacional do motor de debug.")
@click.option('--no-rescue', is_flag=True,
                help="Desativa a interceptação forense da Sotéria/Lazarus.")
@click.option('--test-mode', is_flag=True, 
                help="Autoriza a depuração de scripts em zonas de quarentena (tests/).")
def debug(script, intern, **kwargs):
#def debug(script, intern, audit_rescue, sniff, meta_analysis, **kwargs):
    """🩺 Autópsia Forense, Monitoramento, CPU ou Memória (MPoT-5)."""

    if kwargs.get('no_rescue'):
        os.environ['DOXOADE_RESCUE'] = '0'
        click.secho("🛡️  [SOTERIA] Modo de Resgate DESATIVADO (Fluxo Bruto).", fg="yellow", dim=True)

    from .debug_systems.debug_engine import execute_debug    
    audit_rescue = kwargs.get('audit_rescue')
    meta_analysis = kwargs.get('meta_analysis')
    sniff = kwargs.get('sniff')
    target_args = kwargs.get('target_args')
    target      = intern if intern else script
    is_internal = True if intern else False
    
    if kwargs.get('status'):
        from ..diagnostic.debug_op_sentry import check_infra
        check_infra()
        return
    
    if target and target.startswith('-'):
        click.secho(f" [!] Erro: '{target}' não parece um script válido. "
                    "Verifique se as flags precedem o alvo.", fg='red')
        return

    if not target:
        click.echo(Fore.RED + "Erro: Forneça um script ou use --intern 'comando'.")
        return

    if sniff:
        from ..probes.sniper_probe import run_sniping
        click.echo(f"{Fore.PRIMARY}🎯 [SNIPER LENS] Focando em: {sniff}{Style.RESET_ALL}")
#        run_sniping(script, sniff, args_str=target_args)
        run_sniping(target, sniff, args_str=target_args)
        return

    if audit_rescue or meta_analysis:
        flag = "--audit-rescue" if audit_rescue else "--meta-analysis"
        # PASC 6.6: Localiza o script de diagnótico
        diag_script = "soteria_diagnose.py" if audit_rescue else "meta_analysis.py"
        path = os.path.join(os.path.dirname(__file__), "..", "tools", "vulcan", "diagnostic", "soteria", diag_script)
        import subprocess
        subprocess.run([sys.executable, path], check=False)
        return

    if not script and not intern:
        click.echo(Fore.RED + "Erro: Forneça um script ou use uma flag de auditoria.")
        return

    if meta_analysis:
        # PASC 6.6: Caminho dinâmico
        path = os.path.join(os.path.dirname(__file__), "..", "tools", "vulcan", "diagnostic", "soteria", "meta_analysis.py")
        import subprocess
        subprocess.run([sys.executable, path], check=False)
        return

    is_tracing = sys.gettrace() is not None
    if is_tracing:
        from .debug_systems.debug_engine import run_debug_in_process
        run_debug_in_process(target, **kwargs)
        return

    execute_debug(target, is_internal, **kwargs)