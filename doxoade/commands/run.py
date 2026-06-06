# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/run.py
"""
Comando Run - v83.5 Platinum.
Orquestrador de Execução Híbrida com Suporte a Sniper Lens e Warden Limits.
"""
import os
import sys
import click
import traceback
from doxoade.tools.doxcolors import Fore, Style

@click.command('run')
@click.argument('script', type=click.Path(exists=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED) # <--- ADICIONE ESTA LINHA
@click.option('--flow', '-fl', is_flag=True, help='Rastro de linhas.')
@click.option('--flow-val', is_flag=True, help='Inspeção de variáveis.')
@click.option('--flow-import', is_flag=True, help='Rastro de I/O.')
@click.option('--flow-func', is_flag=True, help='Rastro de funções.')
@click.option('--file', '-f', 'file_target', type=click.Path(exists=True), help='Sniper Lens: Foca rastro neste arquivo.')
@click.option('--target', '-t', 'target_target', help='Alias para --file.')
@click.option('--processing-limiter', '-pl', type=float, help='Limite de CPU em % (ex: 0.5 para 50%).')
@click.option('--ram-limiter', '-rl', type=str, help='Limite de RAM (ex: 512mb, 1gb).')
@click.option('--disk-limiter', '-dl', type=str, help='Limite de escrita em disco (ex: 100mb).')
@click.option('--no-vulcan', is_flag=True, help='Desativa o Turbo Nativo.')
@click.option('--test-mode', is_flag=True, help='Autoriza scripts de teste.')
@click.pass_context
def run(ctx, script, args, **kwargs):
    """Executor Universal v83.5: Decisão Única de Fluxo com Controle de Célula de Carga."""
    from ..rescue_systems.execution_context import ExecutionContext, ExecutionMode
    from doxoade.rescue import activate_protocol
    from doxoade.tools.telemetry_tools.logger import ExecutionLogger
    abs_path = os.path.abspath(script)
    
    # 1. Organiza os limites para o Warden
    limits = {
        'cpu': kwargs.get('processing_limiter'),
        'ram': kwargs.get('ram_limiter'),
        'disk': kwargs.get('disk_limiter')
    }
    
    context = ExecutionContext.detect(mode=ExecutionMode.SANDBOX)
    sniper_target = kwargs.get('file_target') or kwargs.get('target_target')
    if sniper_target:
        kwargs['target'] = sniper_target

    with ExecutionLogger('run', abs_path, ctx.params):
        from doxoade.tools.aegis.aegis_utils import validate_execution_context
        from .run_systems.run_flow import execute_flow
        from .run_systems.run_c_lang import maybe_run_c_lang
        
        try:
            validate_execution_context(abs_path, kwargs.get('test_mode', False))
            os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'

            # 2. Tenta execução como C/C++ (Warden aplicado internamente no subprocesso)
            if maybe_run_c_lang(abs_path, limits=limits, flow=kwargs.get('flow'), extra_args=list(args)):
                return

            # 3. Se houver flags de flow para Python
            if any([kwargs.get('flow'), kwargs.get('flow_val'), kwargs.get('flow_import'), kwargs.get('flow_func'), sniper_target]):
                execute_flow(script, **kwargs)
                # Nota: O flow runner Python atualmente ignora limites de recursos nativos
                return

            # 4. Execução Híbrida padrão (Python/Vulcan)
            _execute_hybrid_engine(abs_path, not kwargs.get('no_vulcan'), limits)

        except SystemExit as e:
            # Captura o código real (0, 1, ou NTSTATUS)
            code = e.code if isinstance(e.code, int) else 1 if e.code else 0
            if code != 0:
                activate_protocol(traceback.format_exc(), exit_code=code) # <--- FIX: Passar code
            raise e
        except Exception:
            err_data = traceback.format_exc()
            # Para exceções Python puras, o código é 1
            activate_protocol(err_data, exit_code=1) # <--- FIX: Passar 1
            sys.exit(1)

def _execute_hybrid_engine(script_path: str, use_vulcan: bool, limits: dict):
    from doxoade.tools.aegis.warden import apply_resource_limits
    from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
    abs_path = os.path.abspath(script_path)
    
    # Proteção Anti-Binário: Verifica se o arquivo parece texto
    if abs_path.endswith('.exe'):
        raise click.ClickException(f"O motor Python não pode executar o binário '{os.path.basename(abs_path)}'. Use o fluxo C.")

    apply_resource_limits(limits)
    
    abs_path = os.path.abspath(script_path)
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

@click.command('flow')
@click.argument('script', required=True)
#@click.argument('args', nargs=-1, type=click.UNPROCESSED)
@click.argument('raw_args', nargs=-1, type=click.UNPROCESSED) # Renomeado de args para raw_args
@click.pass_context
def flow_command(ctx, script, **kwargs):
    import os, sys, shlex
    from ..probes import flow_runner
    from .run_systems.run_flow import execute_flow

    # 1. ESTERILIZAÇÃO DE CAMINHO (v125.0)
    # Trocamos \ por / para impedir que o Windows delete as barras
    raw_input = script.strip('"\'').replace('\\', '/')
    parts = shlex.split(raw_input)
    target_name = parts[0]
    internal_args = parts[1:]

    # 2. INJEÇÃO DE ESTADO ANTI-BLACKBOX
    flow_runner._STATE['flow_base'] = True
    flow_runner._STATE['core_trace'] = False 

    # Resolve se é arquivo ou comando
    abs_path = os.path.abspath(target_name).replace('\\', '/')
    is_file = os.path.exists(abs_path) and os.path.isfile(abs_path)

    try:
        if not is_file:
            from doxoade.cli import cli
            cmd_obj = cli.get_command(ctx, target_name)
            if cmd_obj:
                def internal_cmd_wrapper():
                    os.environ['PYTHONUNBUFFERED'] = '1'
                    # v128.0: Incepção por Re-Parsing via cli.main (Evita colisão de nomes)
                    new_argv = [target_name] + internal_args
                    cli.main(args=new_argv, standalone_mode=False)
                
                flow_runner.run_flow_internal(internal_cmd_wrapper)
                return

        # EXECUÇÃO DE ARQUIVO
        execute_flow(abs_path, **kwargs)

    except Exception as e:
        import traceback
        # ACIONA SOTÉRIA AUTOMATICAMENTE NO CRASH
        from doxoade.rescue import activate_protocol
        activate_protocol(traceback.format_exc(), exit_code=1)
        sys.exit(1)