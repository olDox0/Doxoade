# -*- coding: utf-8 -*-
# doxoade/cli.py
"""
Ponto de Entrada Principal (Core Router) - v85.0 Platinum.
Orquestrador Zeus: Gerenciamento de Comandos e Ciclo de Vida.
Compliance: OSL-1, PASC-6.1 (Lazy Loading), PASC-8.4.
"""
import sys
import os
import time
import click
import traceback
from importlib import import_module
from doxoade.tools.doxcolors import Fore, Style
#from ._version import __version__
# --- BOOTSTRAP DE AMBIENTE (OSL-10) ---
if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
# --- MOTOR DE CARREGAMENTO DIFERIDO (LAZY ENGINE) ---
class DoxoadeLazyGroup(click.Group):
    """
    Despachante de Comandos (PASC-6.7).
    Reduz pegada de RAM ao carregar módulos apenas sob demanda.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O Mapa da Verdade: Centraliza as rotas para a IA entender o fluxo
        self._lazy_map = {
            'android': 'doxoade.commands.android:android_group',
            'apicheck': 'doxoade.commands.apicheck:apicheck',
            'audit': 'doxoade.commands.audit_cmd:audit',
            'auto': 'doxoade.commands.auto:auto',
            'branch': 'doxoade.commands.git_branch:branch',
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
#            'experimental': 'doxoade.commands.experimental:experimental',
            'flow': 'doxoade.commands.run:flow_command',
            'git-clean': 'doxoade.commands.git_clean:git_clean',
            'git-new': 'doxoade.commands.git_new:git_new',
            'global-health': 'doxoade.commands.global_health:global_health',
            'guicheck': 'doxoade.commands.guicheck:guicheck',
            'hack': 'doxoade.commands.hacking:hack',
            'health': 'doxoade.commands.health:health',
            'history': 'doxoade.commands.history:history',
            'ide': 'doxoade.commands.mobile_ide:ide',
            'impact-analysis': 'doxoade.commands.impact_analysis:impact_analysis',
            'init': 'doxoade.commands.init:init',
            'install': 'doxoade.commands.install:install',
            'intelligence': 'doxoade.commands.intelligence:intelligence',
            'kvcheck': 'doxoade.commands.kvcheck:kvcheck',
            'log': 'doxoade.commands.utils:log',
            'maestro': 'doxoade.commands.maestro:maestro',
            'merge': 'doxoade.commands.git_merge:merge',
            'migrate-colors': 'doxoade.commands.migrate_colors:migrate_colors',
            'migrate-db': 'doxoade.commands.migrate_db:migrate_db',
            'mirror': 'doxoade.commands.mirror:mirror',
            'mk': 'doxoade.commands.utils:mk',
            'moddify': 'doxoade.commands.moddify:moddify',
            'pedia': 'doxoade.commands.pedia:pedia',
            'purge-history': 'doxoade.commands.purge_history:purge_history',
            'pr': 'doxoade.commands.git_pr:pr',
            'python': 'doxoade.commands.python:python',
            'rebuild': 'doxoade.commands.rebuild:rebuild',
            'regression-test': 'doxoade.commands.regression_test:regression_test',
            'release': 'doxoade.commands.git_workflow:release',
            'rescue': 'doxoade.commands.rescue_cmd:rescue',
            'rewind': 'doxoade.commands.rewind:rewind',
            'risk': 'doxoade.commands.risk:risk',
            'run': 'doxoade.commands.run:run',
            'save': 'doxoade.commands.save:save',
            'scaffold': 'doxoade.commands.scaffold:scaffold',
            'search': 'doxoade.commands.search:search',
            'security': 'doxoade.commands.security:security',
            'self-test': 'doxoade.commands.self_test:self_test',
            'setup-health': 'doxoade.commands.utils:setup_health_cmd',
            'show-trace': 'doxoade.commands.utils:show_trace',
            'style': 'doxoade.commands.style:style',
            'sync': 'doxoade.commands.git_workflow:sync',
            'telemetry': 'doxoade.commands.telemetry:telemetry',
            'test': 'doxoade.commands.test:test',
            'timeline': 'doxoade.commands.timeline:timeline',
            'venv-up': 'doxoade.commands.venv_up:venv_up',
            'verilog': 'doxoade.commands.verilog:verilog',
            'vulcan': 'doxoade.commands.vulcan_cmd:vulcan_group',
            'webcheck': 'doxoade.commands.webcheck:webcheck',
        }
    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())
    def get_command(self, ctx, name):
        if name not in self._lazy_map: return None
        module_path, attr_name = self._lazy_map[name].split(':')
        try:
            mod = import_module(module_path)
            return getattr(mod, attr_name)
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
            self._print_fatal_import(name, e)
            return None
    def _print_fatal_import(self, cmd_name, e):
        print(f"\033[31m\n[ FATAL ] Erro ao carregar comando '{cmd_name}'")
        print(f"   ■ Causa: {e}\033[0m")
        if '--debug' in sys.argv: traceback.print_exc()
# --- ORQUESTRADOR PRINCIPAL ---
@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard', is_flag=True, help="Verificação de integridade Aegis.")
@click.pass_context
def cli(ctx, guard):
    """olDox222 Advanced Development Environment (doxoade)."""
    ctx.ensure_object(dict)
    
    # 1. Persistência (Osíris)
    from doxoade.tools.db_utils import start_persistence_worker
    start_persistence_worker()
    
    # 2. Banco de Dados (Ma'at)
    from doxoade.database import init_db
    try: init_db()
    except Exception as e:
        click.secho(f"Falha na integridade da base: {e}", fg='red')
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        sys.exit(1)
    # 3. Telemetria (Chronos)
    if ctx.invoked_subcommand:
        from doxoade.chronos import chronos_recorder
        ctx.obj['start_time'] = time.perf_counter()
        chronos_recorder.start_command(ctx)
    else:
        click.echo(ctx.get_help())
@cli.result_callback()
def process_result(result, **kwargs):
    """Sela a execução e finaliza telemetria (PASC-8.20)."""
    ctx = click.get_current_context()
    if ctx.obj and 'start_time' in ctx.obj:
        duration_ms = (time.perf_counter() - ctx.obj['start_time']) * 1000
        exit_code = 0 if sys.exc_info()[0] is None else 1
        from doxoade.chronos import chronos_recorder
        try:
            chronos_recorder.end_command(exit_code, duration_ms)
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_number = exc_tb.tb_lineno
            print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
            exc_trace(exc_tb)
# --- FUNÇÃO DE ENTRADA (BOOTSTRAP) ---
def main():
    """Wrapper blindado com Injeção Vulcan (Hefesto)."""
    
    # 1. Prioridade Vulcan (PASC-6.4)
    project_root = os.getcwd()
    vulcan_bin = os.path.join(project_root, ".doxoade", "vulcan", "bin")
    if os.path.exists(vulcan_bin) and vulcan_bin not in sys.path:
        sys.path.insert(0, vulcan_bin)
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.secho("\n[!] Operação cancelada pelo usuário.", fg='yellow')
        sys.exit(130)
# [DOX-UNUSED]     except Exception as e:
        # PASC-1.1: Captura o rastro completo antes de enviar para o resgate
        import traceback
        err_full_text = traceback.format_exc() 
        
        from doxoade.rescue import analyze_crash
        print(f"\n{Fore.RED}{Style.BRIGHT}[ NUCLEUS CRASH ]")
        
        # Correção: Passa o texto formatado, não o objeto de exceção
        analyze_crash(err_full_text) 
        sys.exit(1)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"\033[31m ■ Archibe: {fname} - line: {line_number}  \n ■ Exception type: {e} . . .\n  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
    finally:
        from doxoade.tools.db_utils import stop_persistence_worker
        stop_persistence_worker()
if __name__ == "__main__":
    main()