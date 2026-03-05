# -*- coding: utf-8 -*-
# doxoade/commands/run.py (v83.3 Omega - Stability Fix)
"""
Comando Run - v83.3 Omega.
Orquestrador de Execução Híbrida com Suporte a Sniper Lens.
"""
import os
import click
from doxoade.tools.doxcolors import Fore
from ..shared_tools import ExecutionLogger
from .run_systems.run_flow import execute_flow
from .run_systems.run_vulcan import apply_vulcan_turbo
from ..rescue_systems.execution_context import ExecutionContext, ExecutionMode

@click.command('run')
@click.argument('script', type=click.Path(exists=True))
@click.option('--flow', '-fl', is_flag=True, help="Rastro de linhas.")
@click.option('--flow-val', is_flag=True, help="Inspeção de variáveis.")
@click.option('--flow-import', is_flag=True, help="Rastro de I/O.")
@click.option('--flow-func', is_flag=True, help="Rastro de funções.")
@click.option('--file', '-f', 'file_target', type=click.Path(exists=True), help="Sniper Lens: Foca rastro neste arquivo.")
@click.option('--target', '-t', 'target_target', help="Alias para --file.")
@click.option('--no-vulcan', is_flag=True, help="Desativa o Turbo Nativo.")
@click.option('--test-mode', is_flag=True, help="Autoriza scripts de teste.")
@click.pass_context
def run(ctx, script: str, **kwargs): # FIX: Adicionada a vírgula faltante
    """Executor Universal v83.3: Decisão Única de Fluxo."""
    abs_path = os.path.abspath(script)

    context = ExecutionContext.detect( #noqa
        mode=ExecutionMode.SANDBOX
    )
    
    # Consolida o alvo do Sniper Lens (-f ou -t)
    sniper_target = kwargs.get('file_target') or kwargs.get('target_target')
    if sniper_target:
        kwargs['target'] = sniper_target
    with ExecutionLogger('run', abs_path, ctx.params):
        from ..tools.security_utils import validate_execution_context
        
        # 1. ROTEAMENTO DE FLUXO (Brancheamento Único)
        if any([kwargs.get('flow'), kwargs.get('flow_val'), 
                kwargs.get('flow_import'), kwargs.get('flow_func'), 
                sniper_target]):
            # MODO MATRIX: In-Process com Rastro
            execute_flow(script, **kwargs)
#        else:
#            # MODO TURBO: In-Process com Injeção Vulcan
#            _execute_hybrid_engine(abs_path, not kwargs.get('no_vulcan'))
        
        # 2. Validação de Contexto (Aegis Rule 19)
        try:
            # Sincroniza ambiente e autoriza execução
            validate_execution_context(abs_path, kwargs.get('test_mode', False))
            os.environ["DOXOADE_AUTHORIZED_RUN"] = "1"
            
            _execute_hybrid_engine(abs_path, not kwargs.get('no_vulcan'))
                
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            raise e
def _execute_hybrid_engine(script_path: str, use_vulcan: bool):
    abs_path = os.path.abspath(script_path)
    from ..tools.security_utils import restricted_safe_exec
    
    # O label só é HYBRID se o Chief permitir e o binário NÃO estiver stale
    # Mas para a UI, mostramos HYBRID se a tentativa de injeção for autorizada
    label = "HYBRID" if use_vulcan else "PYTHON"
    color = Fore.CYAN if use_vulcan else Fore.WHITE
    globs = {'__name__': '__main__', '__file__': abs_path}
    if use_vulcan:
        # Tenta injetar. Se for stale, a função não fará nada (PASC-2)
        apply_vulcan_turbo(abs_path, globs)
    try:
        click.echo(color + f"--- [RUN:{label}] Executing: {os.path.basename(abs_path)} ---")
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        restricted_safe_exec(content, globs, allow_imports=True, filename=abs_path)
    except Exception as e:
        raise e
@click.command('flow')
@click.argument('script', type=click.Path(exists=True))
@click.pass_context
def flow_command(ctx, script):
    """Alias imediato para 'doxoade run --flow' (PASC 6.5)."""
    # Invoca o comando run original com a flag flow ativa
    ctx.invoke(run, script=script, flow=True)