# doxoade/doxoade/cli.py
"""
Ponto de Entrada Principal (Core Router) - v85.1 Platinum.
Orquestrador Zeus: Gerenciamento de Comandos e Ciclo de Vida.
Compliance: OSL-1, PASC-6.1 (Lazy Loading), PASC-8.4.
"""
import sys
import os
import time
import click
import traceback
from importlib import import_module
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        
        # Lógica simplificada para evitar erro de aspas no f-string
        exc_val = str(exc_obj).replace("'", "")
        print(f"\x1b[31m ■ Archive: {fname} - line: {line_number}")
        print(f" ■ Exception type: {type(e).__name__}")
        print(f" ■ Exception value: {exc_val}\x1b[0m")
        exc_trace(exc_tb)

class DoxoadeLazyGroup(click.Group):
    """
    Despachante de Comandos (PASC-6.7).
    Reduz pegada de RAM ao carregar módulos apenas sob demanda.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_map = {
        #'COMANDO': 'DIRETORIO.DO.COMANDO:FUNÇÃO_DO_COMANDO', 
        'android': 'doxoade.commands.android:android_group', 
        'apicheck': 'doxoade.commands.apicheck:apicheck', 
        'audit': 'doxoade.commands.audit_cmd:audit', 
        'auto': 'doxoade.commands.auto:auto', 
        'branch': 'doxoade.commands.git_branch:branch', 
        'canonize': 'doxoade.commands.canonize:canonize', 
        'check': 'doxoade.commands.check:check', 
        'clean': 'doxoade.commands.clean:clean', 
        'compress': 'doxoade.commands.compress_systems.compress_cmd:compress_cmd',
        'config': 'doxoade.commands.config:config_group', 
        'create-pipeline': 'doxoade.commands.utils:create_pipeline', 
        'dashboard': 'doxoade.commands.dashboard:dashboard', 
        'db-query': 'doxoade.commands.db_query:db_query', 
        'debug': 'doxoade.commands.debug:debug', 
        'deepcheck': 'doxoade.commands.deepcheck:deepcheck', 
        'diagnose': 'doxoade.commands.diagnose:diagnose', 
        'diff': 'doxoade.commands.diff:diff', 
        'doctor': 'doxoade.commands.doctor:doctor', 
        'doxcolors': 'doxoade.commands.doxcolors_systems.colors_command:doxcolors_cmd', 
        'encoding': 'doxoade.commands.encoding:encoding', 
        'fix': 'doxoade.commands.fix:fix', 
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
        'lab': 'doxoade.commands.lab:lab_group',
        'linux': 'doxoade.commands.linux_systems.linux_cmd:linux_group',
        'log': 'doxoade.commands.utils:log', 
        'maestro': 'doxoade.commands.maestro:maestro', 
        'merge': 'doxoade.commands.git_merge:merge', 
        'migrate-db': 'doxoade.commands.migrate_db:migrate_db', 
        'mirror': 'doxoade.commands.mirror:mirror', 
        'mk': 'doxoade.commands.utils:mk', 
        'moddify': 'doxoade.commands.moddify:moddify', 
        'panel':  'doxoade.commands.panel_command:panel_command',
        'pedia': 'doxoade.commands.pedia:pedia', 
        'purge-history': 'doxoade.commands.purge_history:purge_history', 
        'pr': 'doxoade.commands.git_pr:pr', 
        'python': 'doxoade.commands.python:python', 
        'rebuild': 'doxoade.commands.rebuild:rebuild', 
        'refactor': 'doxoade.commands.refactor_systems.refactor_command:refactor_group', 
        'regression-test': 'doxoade.commands.regression_test:regression_test', 
        'release': 'doxoade.commands.git_workflow:release', 
        'rescue': 'doxoade.commands.rescue_cmd:rescue', 
        'rewind': 'doxoade.commands.rewind:rewind', 
        'risk': 'doxoade.commands.risk:risk', 
        'run': 'doxoade.commands.run:run', 
        'save': 'doxoade.commands.save:save', 
        'search': 'doxoade.commands.search:search', 
        'security': 'doxoade.commands.security_systems.security_cmd:security', 
        'self-test': 'doxoade.commands.self_test:self_test', 
        'setup-health': 'doxoade.commands.utils:setup_health_cmd', 
        'show-trace': 'doxoade.commands.utils:show_trace', 
        'style': 'doxoade.commands.style:style', 
        'sync': 'doxoade.commands.git_workflow:sync', 
        'telemetry': 'doxoade.commands.telemetry:telemetry', 
        'terminal': 'doxoade.commands.shell_systems.shell_cmd:terminal', 
        'termux-config': 'doxoade.commands.termux_command:termux_config', 'test': 'doxoade.commands.test:test', 
        'timeline': 'doxoade.commands.timeline:timeline', 
        'venvkeeper': 'doxoade.commands.venvkeeper_systems.venvkeeper:venvkeeper', 
        'venv': 'doxoade.commands.venv_cmd:venv_cmd',#        'venv-up': 'doxoade.commands.venv_up:venv_up', 
        'verilog': 'doxoade.commands.verilog:verilog', 
        'vulcan': 'doxoade.commands.vulcan_cmd:vulcan_group', 
        'webcheck': 'doxoade.commands.webcheck:webcheck',
        'wsl': 'doxoade.commands.shell_systems.shell_cmd:wsl_shell',
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
        except (ImportError, ModuleNotFoundError) as e:
            missing_module = str(e).split("'")[-2] if "'" in str(e) else str(e)
            
            # --- CRÍTICO: Filtro Anti-Poluição ---
            # Se o erro for em um módulo interno ou se o auto-reparo não for desejado
            if missing_module.startswith('doxoade') or ".commands." in module_path:
                self._print_fatal_import(name, e)
                return None

            # Auto-reparo apenas para bibliotecas externas conhecidas
            click.secho(f"[*] Dependência externa '{missing_module}' ausente. Tentar auto-reparo? [y/N]", fg='yellow')
            # Aqui você poderia colocar um input(), mas por segurança vamos apenas logar o erro
            self._print_fatal_import(name, e)
            return None

    def _print_fatal_import(self, cmd_name, e):
        print(f"\x1b[31m\n[ FATAL ] Erro ao carregar comando '{cmd_name}'")
        print(f'   ■ Causa: {e}\x1b[0m')
        if '--debug' in sys.argv:
            traceback.print_exc()

@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard', is_flag=True, help='Verificação de integridade Aegis.')
@click.pass_context
def cli(ctx, guard):
    """olDox222 Advanced Development Environment (doxoade)."""
    ctx.ensure_object(dict)
    from doxoade.tools.db_utils import start_persistence_worker
    start_persistence_worker()
    from doxoade.database import init_db
    try:
        init_db()
    except Exception as e:
        click.secho(f'Falha na integridade da base: {e}', fg='red')
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        
        # Lógica simplificada para evitar erro de aspas no f-string
        exc_val = str(exc_obj).replace("'", "")
        print(f"\x1b[31m ■ Archive: {fname} - line: {line_number}")
        print(f" ■ Exception type: {type(e).__name__}")
        print(f" ■ Exception value: {exc_val}\x1b[0m")
        exc_trace(exc_tb)
        sys.exit(1)
    if ctx.invoked_subcommand:
        from doxoade.chronos import chronos_recorder
        ctx.obj['start_time'] = time.perf_counter()
        chronos_recorder.start_command(ctx)
    else:
        click.echo(ctx.get_help())

@cli.result_callback()
def process_result(result, **kwargs):
    """
    Sela a execução e finaliza telemetria (PASC-8.20).

    Caminho feliz: chamado pelo Click antes do sys.exit(0) do standalone_mode.
    Caminho de emergência: se nunca for chamado, o atexit em ChronosRecorder
    garante que end_command seja executado com o exit_code inferido.
    """
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
            
            # Lógica simplificada para evitar erro de aspas no f-string
            exc_val = str(exc_obj).replace("'", "")
            print(f"\x1b[31m ■ Archive: {fname} - line: {line_number}")
            print(f" ■ Exception type: {type(e).__name__}")
            print(f" ■ Exception value: {exc_val}\x1b[0m")
            exc_trace(exc_tb)

def main():
    """Wrapper blindado com:
    Injeção Vulcan e Auto-VENV."""
    # === usa o venv ===
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    venv_libs = os.path.join(project_root, 'venv', 'Lib', 'site-packages')
    if os.path.exists(venv_libs):
        sys.path.insert(0, venv_libs)
    # === auto venv ===
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_site_packages = os.path.join(base_dir, 'venv', 'Lib', 'site-packages')
    if os.path.exists(venv_site_packages):
        if venv_site_packages not in sys.path:
            sys.path.insert(0, venv_site_packages)
    # === vulcan execution inject ===
    project_root = os.getcwd()
    vulcan_bin = os.path.join(project_root, '.doxoade', 'vulcan', 'bin')
    if os.path.exists(vulcan_bin) and vulcan_bin not in sys.path:
        sys.path.insert(0, vulcan_bin)
    _exit_code = 0
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.secho('\n[!] Operação cancelada pelo usuário.', fg='yellow')
        _exit_code = 130
    except SystemExit as se:
        _exit_code = se.code if isinstance(se.code, int) else 1 if se.code else 0
        if _exit_code not in (0, 130):
            raise
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        
        # Lógica simplificada para evitar erro de aspas no f-string
        exc_val = str(exc_obj).replace("'", "")
        print(f"\x1b[31m ■ Archive: {fname} - line: {line_number}")
        print(f" ■ Exception type: {type(e).__name__}")
        print(f" ■ Exception value: {exc_val}\x1b[0m")
        exc_trace(exc_tb)
        _exit_code = 1
    finally:
        from doxoade.tools.db_utils import stop_persistence_worker
        stop_persistence_worker()
if __name__ == '__main__':
    main()