# doxoade/doxoade/commands/run.py
"""
Comando Run - v83.3 Omega.
Orquestrador de Execução Híbrida com Suporte a Sniper Lens.
"""
import os
import click
from doxoade.tools.aegis.aegis_utils import validate_execution_context
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.tools.doxcolors import Fore, Style

@click.command('run')
@click.argument('script', type=click.Path(exists=True))
@click.option('--flow', '-fl', is_flag=True, help='Rastro de linhas.')
@click.option('--flow-val', is_flag=True, help='Inspeção de variáveis.')
@click.option('--flow-import', is_flag=True, help='Rastro de I/O.')
@click.option('--flow-func', is_flag=True, help='Rastro de funções.')
@click.option('--file', '-f', 'file_target', type=click.Path(exists=True), help='Sniper Lens: Foca rastro neste arquivo.')
@click.option('--target', '-t', 'target_target', help='Alias para --file.')
@click.option('--no-vulcan', is_flag=True, help='Desativa o Turbo Nativo.')
@click.option('--test-mode', is_flag=True, help='Autoriza scripts de teste.')
@click.pass_context
def run(ctx, script: str, **kwargs):
    """Executor Universal v83.3: Decisão Única de Fluxo."""
    from ..rescue_systems.execution_context import ExecutionContext, ExecutionMode
    abs_path = os.path.abspath(script)
    context = ExecutionContext.detect(mode=ExecutionMode.SANDBOX)
    sniper_target = kwargs.get('file_target') or kwargs.get('target_target')
    if sniper_target:
        kwargs['target'] = sniper_target
    with ExecutionLogger('run', abs_path, ctx.params):
        from .run_systems.run_flow import execute_flow
        from .run_systems.run_c_lang import maybe_run_c_lang
        try:
            validate_execution_context(abs_path, kwargs.get('test_mode', False))
            os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
            if maybe_run_c_lang(abs_path):
                return
            if any([kwargs.get('flow'), kwargs.get('flow_val'), kwargs.get('flow_import'), kwargs.get('flow_func'), sniper_target]):
                execute_flow(script, **kwargs)
            _execute_hybrid_engine(abs_path, not kwargs.get('no_vulcan'))
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f"\x1b[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split("'"))}\x1b[0\n")
            exc_trace(exc_tb)
            raise e

def _execute_hybrid_engine(script_path: str, use_vulcan: bool):
    abs_path = os.path.abspath(script_path)
    from doxoade.tools.doxcolors import Fore
    label = 'HYBRID' if use_vulcan else 'PYTHON'
    color = Fore.CYAN if use_vulcan else Fore.WHITE
    globs = {'__name__': '__main__', '__file__': abs_path}
    if use_vulcan:
        from .run_systems.run_vulcan import apply_vulcan_turbo
        apply_vulcan_turbo(abs_path, globs)
    try:
        click.echo(color + f'--- [RUN:{label}] Executing: {os.path.basename(abs_path)} ---\x1b[0m')
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        restricted_safe_exec(content, globs, allow_imports=True, filename=abs_path)
    except Exception as e:
        raise e

@click.command('flow', context_settings=dict(
    ignore_unknown_options=True, # Permite capturar -s, -i, etc
    allow_extra_args=True,        # Permite argumentos extras
))
@click.argument('target_chain', nargs=-1, required=True) # Captura tudo como uma tupla
@click.pass_context
def flow_command(ctx, target_chain):
    """🌊 Nexus Flow: Rastro de execução para Scripts ou Comandos internos."""
    from doxoade.tools.doxcolors import colors, Fore, Style
    import os
    import sys

    # target_chain será algo como ('doxcolors', 'load', 'file.nxa', '-s', '5')
    target_name = target_chain[0]
    remaining_args = list(target_chain[1:])

    # 1. Caso: É um arquivo .py existente
    if os.path.exists(target_name) and target_name.endswith('.py'):
        # Re-invoca o comando 'run' com as flags de flow
        # Como o 'run' espera kwargs, passamos os argumentos via ctx
        ctx.invoke(run, script=target_name, flow=True)
        return

    # 2. Caso: É um comando interno do doxoade
    # Pegamos o CLI principal (que é o pai do contexto atual)
    main_cli = ctx.parent.command
    cmd_obj = main_cli.get_command(ctx, target_name)

    if not cmd_obj:
        click.echo(f"{Fore.RED}✘ Comando ou arquivo '{target_name}' não encontrado.{Style.RESET_ALL}")
        return

    click.echo(f"{Fore.CYAN}🌊 Injetando Sonda Nexus Flow em: {Fore.YELLOW}{' '.join(target_chain)}{Style.RESET_ALL}")
    
    # Ativa o rastro interno (Noise Gate Open)
    os.environ['DOXOADE_INTERNAL_FLOW'] = '1'
    
    # 3. Execução com Sonda Ativa
    # Importamos o flow_runner apenas aqui para evitar carga desnecessária
    from doxoade.probes import flow_runner
    
    # Criamos um wrapper para executar o comando click dentro do tracer
    def internal_cmd_wrapper():
        try:
            # Executa o comando click com os argumentos restantes
            # standalone_mode=False impede que o click dê sys.exit() ao terminar
            cmd_obj.main(args=remaining_args, standalone_mode=False, parent=ctx)
        except Exception as e:
            raise e

    # O flow_runner agora recebe o wrapper em vez de um path
    try:
        # Precisamos de um pequeno ajuste no flow_runner para aceitar callable
        flow_runner.run_flow_internal(internal_cmd_wrapper)
    except Exception as e:
        click.echo(f"{Fore.RED}🚨 Falha na Sonda Interna: {e}{Style.RESET_ALL}")
