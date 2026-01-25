# doxoade/cli.py
"""
Ponto de Entrada Principal (Core Router).
Implementa Lazy Loading para otimização de RAM (PASC-6.1) e 
Isolamento de Responsabilidade (MPoT-17).
"""
import time
import sys
import os
import click
# [DOX-UNUSED] from typing import Optional
from importlib import import_module
from colorama import init as colorama_init, Fore
# [DOX-UNUSED] from functools import wraps
# [DOX-UNUSED] from datetime import datetime


# 1. Configuração de Ambiente (Bootstrap)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

colorama_init(autoreset=True)

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PARENT = os.path.dirname(PACKAGE_DIR)
if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)

__version__ = "63.0 Alfa (Lazy-Gold)"

# 2. Gerenciador de Carregamento Diferido (Lazy Engine)
class DoxoadeLazyGroup(click.Group):
    """
    Despachante inteligente: Só importa o módulo do comando se ele for invocado.
    Reduz o tempo de startup em ~80% (PASC-6.1).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mapeamento explícito: 'comando': 'modulo:atributo'
        self._lazy_map = {
# [sicdox]            'agent': 'doxoade.commands.agent:agent_cmd',
#            'alfagold': 'doxoade.commands.alfagold:alfagold',
            'android': 'doxoade.commands.android:android_group',
            'apicheck': 'doxoade.commands.apicheck:apicheck',
            'auto': 'doxoade.commands.auto:auto',
# [sicdox]            'brain': 'doxoade.commands.brain:brain',
            'canonize': 'doxoade.commands.canonize:canonize',
            'check': 'doxoade.commands.check:check',
            'clean': 'doxoade.commands.clean:clean',
            'config': 'doxoade.commands.config:config_group',
            'create-pipeline': 'doxoade.commands.utils:create_pipeline',
            'dashboard': 'doxoade.commands.dashboard:dashboard',
            'db-query': 'doxoade.commands.db_query:db_query',
            'debug': 'doxoade.commands.debug:debug',
            'deepcheck': 'doxoade.commands.deepcheck:deepcheck',
            'diagnose': 'doxoade.commands.diagnose:diagnose',
            'diff': 'doxoade.commands.diff:diff',
            'doctor': 'doxoade.commands.doctor:doctor',
            'encoding': 'doxoade.commands.encoding:encoding',
            'flow': 'doxoade.commands.run:flow_command',
            'git-clean': 'doxoade.commands.git_clean:git_clean',
            'git-new': 'doxoade.commands.git_new:git_new',
            'global-health': 'doxoade.commands.global_health:global_health',
            'guicheck': 'doxoade.commands.guicheck:guicheck',
            'hack': 'doxoade.commands.hacking:hack',
            'health': 'doxoade.commands.health:health',
            'history': 'doxoade.commands.history:history',
            'ide': 'doxoade.commands.mobile_ide:ide',
            'ide-setup': 'doxoade.commands.mobile_ide:ide_setup',
            'impact-analysis': 'doxoade.commands.impact_analysis:impact_analysis',
            'init': 'doxoade.commands.init:init',
            'install': 'doxoade.commands.install:install',
            'intelligence': 'doxoade.commands.intelligence:intelligence',
            'kvcheck': 'doxoade.commands.kvcheck:kvcheck',
#            'lab': 'doxoade.commands.lab:lab',
#            'lab-ast': 'doxoade.commands.lab_ast:lab_ast',
            'log': 'doxoade.commands.utils:log',
            'maestro': 'doxoade.commands.maestro:maestro',
            'merge': 'doxoade.commands.git_merge:merge',
            'migrate-db': 'doxoade.commands.migrate_db:migrate_db',
            'mirror': 'doxoade.commands.mirror:mirror',
            'mk': 'doxoade.commands.utils:mk',
            'moddify': 'doxoade.commands.moddify:moddify',
            'pedia': 'doxoade.commands.pedia:pedia',
            'python': 'doxoade.commands.python:python',
            'rebuild': 'doxoade.commands.rebuild:rebuild',
            'regression-test': 'doxoade.commands.regression_test:regression_test',
            'release': 'doxoade.commands.git_workflow:release',
            'rewind': 'doxoade.commands.rewind:rewind',
            'risk': 'doxoade.commands.risk:risk',
            'run': 'doxoade.commands.run:run',
            'save': 'doxoade.commands.save:save',
            'scaffold': 'doxoade.commands.scaffold:scaffold',
            'search': 'doxoade.commands.search:search',
            'security': 'doxoade.commands.security:security',
            'self-test': 'doxoade.commands.self_test:self_test',
            'setup-health': 'doxoade.commands.utils:setup_health_cmd',
            'setup-regression': 'doxoade.commands.utils:setup_regression',
#            'sicdox': 'doxoade.commands.sicdox:sicdox_group',
            'show-trace': 'doxoade.commands.utils:show_trace',
            'style': 'doxoade.commands.style:style',
            'sync': 'doxoade.commands.git_workflow:sync',
            'telemetry': 'doxoade.commands.telemetry:telemetry',
            'test': 'doxoade.commands.test:test',
            'test-map': 'doxoade.commands.test_mapper:test_map',
# [sicdox]            'think': 'doxoade.commands.think:think',
            'timeline': 'doxoade.commands.timeline:timeline',
            'tutorial': 'doxoade.commands.tutorial:tutorial_group',
            'venv-up': 'doxoade.commands.venv_up:venv_up',
            'verilog': 'doxoade.commands.verilog:verilog',
            'webcheck': 'doxoade.commands.webcheck:webcheck',
        }

    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())

    def get_command(self, ctx, name):
        if name not in self._lazy_map:
            return None
        
        module_path, attr_name = self._lazy_map[name].split(':')
        try:
            mod = import_module(module_path)
            return getattr(mod, attr_name)
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            _, exc_obj, exc_tb = _dox_sys.exc_info()
            
            # Navega no traceback para encontrar o erro real no módulo de comando
            while exc_tb.tb_next:
                exc_tb = exc_tb.tb_next
            
            fname = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            
            # Chief-Gold Forensic UI
            click.echo(f"\033[1;34m[ LAZY-LOAD FAIL ]\033[0m \033[1mCommand: {name}\033[0m")
            click.echo(f"   \033[31m■ Archive : {fname} (Line: {line_number})")
            click.echo(f"   ■ Exception: {type(e).__name__}: {e}\033[0m")
            return None
            
# 3. Grupo Principal
@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard', is_flag=True, help="Ativa a verificação de integridade antes da execução.")
@click.pass_context
def cli(ctx, guard):
    """olDox222 Advanced Development Environment (doxoade) v14"""
    ctx.ensure_object(dict)
    
    # PASC-3: Inicia worker de persistência logo no início
    from doxoade.tools.db_utils import start_persistence_worker
    start_persistence_worker()
    
    # 6.2: Inicialização explícita do banco
    from doxoade.database import init_db
    try:
        init_db()
    except Exception as e:
        click.echo(f"{Fore.RED}Falha crítica no banco: {e}")
        sys.exit(1)

    if guard:
        # PASC-8: Chama a verificação antes de qualquer comando
        from .commands.hacking import verify_silent
        if not verify_silent():
            click.echo(Fore.RED + "Execução bloqueada por falha de integridade.")
            sys.exit(1)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
    else:
        # Chronos: Importado localmente para economizar RAM
        from doxoade.chronos import chronos_recorder
        ctx.obj['start_time'] = time.perf_counter()
        try:
            chronos_recorder.start_command(ctx)
        except Exception: 
            pass

@cli.result_callback()
def process_result(result, **kwargs):
    """Encerramento de Telemetria e Auditoria Chronos."""
    ctx = click.get_current_context()
    if ctx.obj and 'start_time' in ctx.obj:
        duration_ms = (time.perf_counter() - ctx.obj['start_time']) * 1000
        exit_code = 0 if sys.exc_info()[0] is None else 1
        
        from doxoade.chronos import chronos_recorder
        try:
            chronos_recorder.end_command(exit_code, duration_ms)
        except Exception: 
            pass

# Comandos de Diagnóstico do Core (Lazy inside commands/utils)
@cli.command('self-diagnose')
def self_diagnose():
    from .diagnostic.check_diagnose import verificar_integridade_sondas
    verificar_integridade_sondas()

@cli.command('directory-diagnose')
def dir_diagnose_cmd():
    from .diagnostic.directory_diagnose import executar_diagnostico_diretorio
    if executar_diagnostico_diretorio():
        click.echo(f"{Fore.GREEN}\n[OK] Infraestrutura de diretórios validada.")
    else:
        click.echo(f"{Fore.RED}\n[FALHA] O sistema se perde em subpastas.")

#@click.group('sicdox')
#def sicdox():
#    """Sistemas Cognitivos do Doxoade: Unificação de IA e Automação."""
#    pass
#
## Adicionamos os subcomandos ao grupo
#@sicdox.command('directory')
#@click.argument('path', default='.')
#def sicdox_directory(path):
#    """Audita a percepção de pastas do SiCDox."""
#    from .diagnostic.directory_diagnose import auditar_percepcao_espacial
#    auditar_percepcao_espacial(path)

def main():
    """Wrapper de execução blindado com encerramento de logs."""
    from doxoade.tools.db_utils import stop_persistence_worker
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.echo(f"{Fore.YELLOW}\n[!] Interrupção manual. Finalizando...")
        sys.exit(130)
    except Exception as e:
        from doxoade.rescue import analyze_crash
        analyze_crash(e)
        sys.exit(1)
    finally:
        # GARANTIA GOLD: Esvazia o buffer de logs antes de fechar o processo
        stop_persistence_worker()

if __name__ == '__main__':
    main()