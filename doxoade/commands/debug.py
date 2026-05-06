# doxoade/doxoade/commands/debug.py
"""
Debug Suite v2.1 - Chief Gold Orchestrator.
Compliance: MPoT-1, PASC-1.
"""
import click

@click.command('debug')
@click.argument('script', required=False) # Agora script é opcional se usar --intern
@click.option(  '--args',  help='Args do script.')
@click.option(  '--watch', help='Monitora uma variável em tempo real.')
@click.option(  '--intern',      '-i',                help='Executa e depura um comando interno. Ex: --intern "check ."')
@click.option(  '--bottleneck',  '-b',  is_flag=True, help='Exibe linhas com tempo por linha.')
@click.option(  '--no-compress', '-nc', is_flag=True, help='Desativa compressão de loops repetidos.')
@click.option(  '--profile',     '-p',  is_flag=True, help='Perfil de CPU (tempo).')
@click.option(  '--memory',      '-m',  is_flag=True, help='Autópsia profunda de Memória (GC + Tracebacks).')
@click.option(  '--threshold',   '-t',  type=float, default=0.0, help='Filtra linhas abaixo de N ms.')
def debug(script, intern, **kwargs):
# def debug(script, args, watch, bottleneck, no_compress, profile, memory, threshold):
    """🩺 Autópsia Forense, Monitoramento, CPU ou Memória (MPoT-5)."""
    from .debug_systems.debug_engine import execute_debug
    
    target = intern if intern else script
    is_internal = True if intern else False
    
    if not target:
        click.echo(Fore.RED + "Erro: Forneça um script ou use --intern 'comando'.")
        return

    execute_debug(target, is_internal=is_internal, **kwargs)