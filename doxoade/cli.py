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
import json
import inspect
import traceback
from pathlib import Path
from importlib import import_module

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.doxcolors import init as init_colors
from doxoade.tools.command_metadata import COMMAND_META, format_help

# Instala Ganesha Advisor
from doxoade.tools.ganesha_systems import install_ganesha_hook
install_ganesha_hook()


if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as e:
        try:
            from doxoade.tools.error_info import format_traceback
            format_traceback(e, "Encoding Reconfiguration")
        except Exception:
            traceback.print_exception(e)

class DoxoadeLazyGroup(click.Group):
    """
    Despachante de Comandos (PASC-6.7).
    Reduz pegada de RAM ao carregar módulos apenas sob demanda.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_path = Path(".doxoade/help_cache.json")
        self._help_cache = self._load_cache()
        self._lazy_map = {
            'android': 'doxoade.commands.android:android_group',
            'apicheck': 'doxoade.commands.apicheck:apicheck',
            'audit': 'doxoade.commands.audit_cmd:audit',
            'auto': 'doxoade.commands.auto:auto',
            'branch': 'doxoade.commands.git_branch:branch',
            'canonize': 'doxoade.commands.canonize:canonize',
            'check': 'doxoade.commands.check:check',
            'clean': 'doxoade.commands.clean:clean',
            'compress': 'doxoade.commands.compress_systems.compress_cmd:compress_file_cmd',
            'config': 'doxoade.commands.config:config_group',
            'create-pipeline': 'doxoade.commands.utils:create_pipeline',
            'dashboard': 'doxoade.commands.dashboard:dashboard',
            'db-query': 'doxoade.commands.db_query:db_query',
            'db': 'doxoade.commands.db_cmd:db_group',
            'debug': 'doxoade.commands.debug:debug',
            'deepcheck': 'doxoade.commands.deepcheck:deepcheck',
            'diagnose': 'doxoade.commands.diagnose:diagnose',
            'diff': 'doxoade.commands.diff:diff',
            'doctor': 'doxoade.commands.vulcan_systems.vulcan_cmd:doctor',
            'doxcolors': 'doxoade.commands.doxcolors_systems.colors_command:doxcolors_cmd',
            'encoding': 'doxoade.commands.encoding:encoding',
            'engine': 'doxoade.commands.engine_cmd:engine_group',
            'fix': 'doxoade.commands.fix:fix',
            'flow': 'doxoade.commands.run:flow_command',
            'git-clean': 'doxoade.commands.git_clean:git_clean',
            'git-new': 'doxoade.commands.git_new:git_new',
            'global-health': 'doxoade.commands.global_health:global_health',
            'gui': 'doxoade.commands.gui_cmd:gui_group',
            'guicheck': 'doxoade.commands.guicheck:guicheck',
            'hack': 'doxoade.commands.hacking:hack',
            'health': 'doxoade.commands.health:health',
            'hermes':'doxoade.commands.cmd_hermes:hermes_group',
            'history': 'doxoade.commands.history:history',
            'horus': 'doxoade.commands.horus_cmd:horus_group',
            'ide': 'doxoade.commands.mobile_ide:ide',
            'impact-analysis': 'doxoade.commands.impact_analysis:impact_analysis',
            'init': 'doxoade.commands.init:init',
            'install': 'doxoade.commands.install:install',
            'intelligence': 'doxoade.commands.intelligence_systems.intelligence:intelligence',
            'kvcheck': 'doxoade.commands.kvcheck:kvcheck',
            'lab': 'doxoade.commands.lab:lab_group',
            'linux': 'doxoade.commands.linux_systems.linux_cmd:linux_group',
            'log': 'doxoade.commands.utils:log',
            'macrothon': 'doxoade.commands.macrothon_systems.macrothon_builder:macrothon_group',
            'maestro': 'doxoade.commands.maestro:maestro',
            'merge': 'doxoade.commands.git_merge:merge',
            'metal': 'doxoade.commands.metalcraft:metal_group',
            'mirror': 'doxoade.commands.mirror:mirror',
            'mk': 'doxoade.commands.utils:mk',
            'mody': 'doxoade.commands.moddify:moddify',
            'moduloid': 'doxoade.commands.moduloid_systems.moduloid_acervo:moduloid_group',
            'panel': 'doxoade.commands.panel_command:panel_command',
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
            'termux-config': 'doxoade.commands.termux_command:termux_config',
            'test': 'doxoade.commands.test:test',
            'timeline': 'doxoade.commands.timeline:timeline',
            'vault': 'doxoade.commands.vault_cmd:vault_group',
            'venvkeeper': 'doxoade.commands.venvkeeper_systems.venvkeeper:venvkeeper',
            'venv': 'doxoade.commands.venv_cmd:venv_cmd',
            'verilog': 'doxoade.commands.verilog:verilog',
            'vulcan': 'doxoade.commands.vulcan_systems.vulcan_cmd:vulcan_group',
            'webcheck': 'doxoade.commands.webcheck:webcheck',
            'wsl': 'doxoade.commands.linux_systems.linux_cmd:linux_group',

            'flow-diag': 'doxoade.diagnostic.flow_necropsy:run_flow_necropsy',
            'test-shadow': 'doxoade.commands.test_shadow:test_shadow',
            'stress-hades': 'doxoade.commands.stress_test:stress_hades',
            'stress-abyss': 'doxoade.commands.stress_test:stress_abyss',
        }

    def resolve_command(
        self, ctx: click.Context, args: list
    ):
        """Intercepta comandos errados e sugere correções via Ganesha."""
        cmd_name = click.utils.make_str(args[0]) if args else None
        
        # Tenta resolver o comando normalmente
        cmd = self.get_command(ctx, cmd_name)
        
        if cmd is not None:
            return cmd_name, cmd, args[1:]
        
        # Comando não existe - aciona Ganesha
        from doxoade.tools.ganesha_systems.ganesha_advisor import GaneshaAdvisor
        GaneshaAdvisor.show_command_suggestion(ctx, self, cmd_name)
        ctx.exit(1)

    def parse_args(self, ctx: click.Context, args: list) -> list:
        """Intercepta opções erradas no grupo principal e sugere correções via Ganesha."""
        if not args or args[0].startswith('-'):
            try:
                return super().parse_args(ctx, args)
            except click.exceptions.UsageError as e:
                error_msg = str(e)
                if "No such option:" in error_msg:
                    wrong_option = error_msg.split("No such option:")[-1].strip()
                    from doxoade.tools.ganesha_systems.ganesha_advisor import GaneshaAdvisor
                    GaneshaAdvisor.show_option_suggestion(ctx, ctx.command, wrong_option)
                    GaneshaAdvisor.show_usage_suggestion(ctx.command, args)
                    ctx.exit(1)
                elif "Missing argument" in error_msg or "Got unexpected extra argument" in error_msg:
                    from doxoade.tools.ganesha_systems.ganesha_advisor import GaneshaAdvisor
                    GaneshaAdvisor.show_usage_suggestion(ctx.command, args)
                    ctx.exit(1)
                raise
        return super().parse_args(ctx, args)
        
    def _load_cache(self):
        if self._cache_path.exists():
            return json.loads(self._cache_path.read_text())
        return {}

    def _sanitize(self, text: str) -> str:
        import re
        text = re.sub(r'\s*\([^)]*\)', '', text)
        return text.strip()

    def _rebuild_cache(self, force=False):
        import ast

        if '--refresh-help' in sys.argv or force:
            self._help_cache = {}

        base_dir = Path(__file__).resolve().parent.parent

        for name, path in self._lazy_map.items():
            mod_path, attr = path.split(':')
            file_path = base_dir / (mod_path.replace('.', os.sep) + '.py')

            if not file_path.exists():
                self._help_cache[name] = "Comando embutido ou indisponível."
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(content)
                doc = None

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name == attr:
                            doc = ast.get_docstring(node)
                            break

                if doc:
                    raw_doc = doc.strip().split('\n')[0]
                    self._help_cache[name] = self._sanitize(raw_doc)
                else:
                    self._help_cache[name] = ""
            except Exception:
                self._help_cache[name] = ""

        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._help_cache, indent=2), encoding='utf-8')
        except Exception:
            pass

    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())

    def format_commands(self, ctx, formatter):
        if '--refresh-help' in sys.argv:
            self._rebuild_cache(force=True)
        elif not self._help_cache:
            self._rebuild_cache()

        import textwrap
        with formatter.section("Comandos Disponíveis"):
            for name in sorted(self._lazy_map.keys()):
                desc = self._help_cache.get(name, "")

                color = Fore.CYAN
                if any(x in name for x in ['hack', 'security', 'audit']): color = Fore.RED
                elif any(x in name for x in ['db', 'config', 'venv']): color = Fore.YELLOW

                colored_name = f"  {color}{name:<20}{Style.RESET_ALL}"
                wrapped_desc = textwrap.wrap(desc, width=75)

                if not wrapped_desc:
                    formatter.write(f"{colored_name}\n")
                else:
                    formatter.write(f"{colored_name}{wrapped_desc[0]}\n")
                    for line in wrapped_desc[1:]:
                        formatter.write(f"  {' ':<20}{line}\n")

    def get_command(self, ctx, name):
        if name not in self._lazy_map:
            return None
        
        module_path, attr_name = self._lazy_map[name].split(':')
        import importlib.util
        
        # --- ORÁCULO DE SINTAXE ---
        try:
            spec = importlib.util.find_spec(module_path)
            if spec and spec.origin:
                with open(spec.origin, 'r', encoding='utf-8') as f:
                    compile(f.read(), spec.origin, 'exec')
        except SyntaxError:
            from doxoade.rescue import activate_protocol
            activate_protocol(traceback.format_exc())
            return None
        except Exception:
            pass
        
        # --- CARREGAMENTO REAL E INJEÇÃO DE CORES ---
        try:
            mod = import_module(module_path)
            cmd = getattr(mod, attr_name)
            
            # 1. Colore e sanitiza o título/descrição principal do comando
            import re
            base_help = getattr(cmd, 'help', None) or self._help_cache.get(name, "")
            if base_help:
                clean_help = re.sub(r'\x1b\[[0-9;]*m', '', base_help)
                clean_help = self._sanitize(clean_help)
                cmd.help = f"{Fore.CYAN}{Style.BRIGHT}{clean_help}{Style.RESET_ALL}"
            
            # 2. Injeta cores dinâmicas nas flags e opções
            def patch_param(p):
                orig_fn = p.get_help_record
                def patched_get_help_record(ctx_inner):
                    record = orig_fn(ctx_inner)
                    if record:
                        opts, help_txt = record
                        colored_opts = f"{Fore.YELLOW}{opts}{Style.RESET_ALL}"
                        colored_help = f"{Fore.WHITE}{Style.DIM}{help_txt}{Style.RESET_ALL}"
                        return (colored_opts, colored_help)
                    return record
                p.get_help_record = patched_get_help_record
                p._dox_patched = True
            
            for param in cmd.params:
                if not getattr(param, '_dox_patched', False):
                    patch_param(param)
            
            # 3. Subcomandos coloridos
            if isinstance(cmd, click.Group) and not getattr(cmd, '_dox_group_patched', False):
                orig_format_commands = cmd.format_commands
                def patched_format_commands(ctx_inner, formatter):
                    commands = []
                    for sub_name in cmd.list_commands(ctx_inner):
                        sub_cmd = cmd.get_command(ctx_inner, sub_name)
                        if sub_cmd is None:
                            continue
                        
                        help_str = sub_cmd.get_short_help_str(limit=80)
                        
                        if not help_str or help_str == "No help available.":
                            cb = getattr(sub_cmd, 'callback', None)
                            if cb:
                                while hasattr(cb, '__wrapped__'):
                                    cb = cb.__wrapped__
                                if cb:
                                    help_str = inspect.getdoc(cb)
                                
                                if not help_str and cb and hasattr(cb, '__module__'):
                                    try:
                                        import ast
                                        mod_inner = sys.modules.get(cb.__module__)
                                        if mod_inner and hasattr(mod_inner, '__file__'):
                                            fpath = mod_inner.__file__
                                            if fpath.endswith(('.pyd', '.so', '.pyc')):
                                                fpath = os.path.splitext(fpath)[0] + '.py'
                                            if os.path.exists(fpath):
                                                source = open(fpath, 'r', encoding='utf-8', errors='ignore').read()
                                                tree = ast.parse(source)
                                                for node in ast.walk(tree):
                                                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                                        if (hasattr(cb, '__name__') and node.name == cb.__name__) or \
                                                           (hasattr(sub_cmd, 'name') and node.name == sub_cmd.name):
                                                            help_str = ast.get_docstring(node)
                                                            break
                                    except Exception:
                                        pass
                        
                        if not help_str:
                            help_str = "Sem descrição."
                        else:
                            lines = [line for line in str(help_str).strip().split('\n') if line.strip()]
                            help_str = self._sanitize(lines[0]) if lines else "Sem descrição."
                        
                        colored_sub_name = f"{Fore.CYAN}{sub_name}{Style.RESET_ALL}"
                        colored_sub_desc = f"{Style.DIM}{help_str}{Style.RESET_ALL}"
                        commands.append((colored_sub_name, colored_sub_desc))
                    
                    if commands:
                        with formatter.section("Commands"):
                            formatter.write_dl(commands)
                
                cmd.format_commands = patched_format_commands
                cmd._dox_group_patched = True

            # 4. Hook do Ganesha para interceptar erros de sintaxe/ordem nos subcomandos
            if not getattr(cmd, '_ganesha_hooked', False):
                original_parse_args = cmd.parse_args
                def ganesha_parse_args(ctx_inner, args_inner):
                    try:
                        return original_parse_args(ctx_inner, args_inner)
                    except click.exceptions.UsageError as e:
                        error_msg = str(e)
                        if "No such option:" in error_msg:
                            wrong_option = error_msg.split("No such option:")[-1].strip()
                            from doxoade.tools.ganesha_systems.ganesha_advisor import GaneshaAdvisor
                            GaneshaAdvisor.show_option_suggestion(ctx_inner, cmd, wrong_option)
                            GaneshaAdvisor.show_usage_suggestion(cmd, args_inner)
                            ctx_inner.exit(1)
                        elif "Missing argument" in error_msg or "Got unexpected extra argument" in error_msg:
                            from doxoade.tools.ganesha_systems.ganesha_advisor import GaneshaAdvisor
                            GaneshaAdvisor.show_usage_suggestion(cmd, args_inner)
                            ctx_inner.exit(1)
                        raise
                cmd.parse_args = ganesha_parse_args
                cmd._ganesha_hooked = True
            
            return cmd
            
        # 🛡️ FECHAMENTO DO TRY PRINCIPAL (Era aqui que estava o SyntaxError)
        except Exception as e:
            if not ctx.resilient_parsing:
                from doxoade.rescue import activate_protocol
                activate_protocol(traceback.format_exc(), exit_code=1)
            self._print_fatal_import(name, e)
            return None

    def _print_fatal_import(self, cmd_name, e):
        _, _, exc_tb = sys.exc_info()
        traceback.print_tb(exc_tb)
        print(f"\033[1;31m\n[ FATAL ] Erro na Matriz de Comando: '{cmd_name}'\033[0m")
        print("\033[1;34m ■ SUBSISTEMA :\033[0m Intelligence Router")
        print(f"\033[1;34m ■ CAUSA      :\033[0m {e}")


@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard',        is_flag=True, help='Verificação de integridade Aegis.')
@click.option('--refresh-help', is_flag=True, help='Força a atualização do cache de descrições.')
@click.option('--pure',         is_flag=True, help='Inicia sem Shadow Runtime nem MetaFinder (modo mínimo).')
@click.pass_context
#def cli(ctx, **kwargs):
def cli(ctx, guard, refresh_help, pure):
    """olDox222 Advanced Development Environment (doxoade)."""
    # --pure já foi consumido e removido de sys.argv em __main__.py antes do
    # Click rodar; aqui só garantimos que o schema o conhece (--help, parsing).
    from doxoade.tools.log_filter import CLILogFilter
    CLILogFilter.suppress_db_traces()

    from doxoade.tools.system_utils import auto_vaccinate_env
    auto_vaccinate_env()
    init_colors(autoreset=True)
    ctx.ensure_object(dict)

    from doxoade.tools.db_utils import start_persistence_worker
    start_persistence_worker()
    from doxoade.core_database import init_db
    try:
        init_db()
    except Exception as e:
        click.secho(f'Falha na integridade da base: {e}', fg='red')
        try:
            from doxoade.tools.error_info import format_traceback
            format_traceback(e, "init_db")
        except Exception:
            traceback.print_exception(e)
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
            try:
                from doxoade.tools.error_info import format_traceback
                format_traceback(e, "process_result - chronos")
            except Exception:
                traceback.print_exception(e)


def main():
    """Wrapper blindado com injeção Vulcan e Auto-VENV."""
    os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'

    # Instala Ganesha Advisor para interceptar erros de CLI
    from doxoade.tools.ganesha_systems import install_ganesha_hook
    install_ganesha_hook()

    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e:
            try:
                from doxoade.tools.error_info import format_traceback
                format_traceback(e, "Encoding Reconfiguration")
            except Exception:
                traceback.print_exception(e)

    # Injeta venv no sys.path se necessário
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    venv_candidates = [
        os.path.join(project_root, 'venv', 'Lib', 'site-packages'),
        os.path.join(project_root, 'venv', 'lib', 'site-packages'),
    ]
    for venv_path in venv_candidates:
        if os.path.exists(venv_path) and venv_path not in sys.path:
            sys.path.insert(0, venv_path)
            break

    # Injeta bin/ do Vulcan no sys.path
    vulcan_bin = os.path.join(os.getcwd(), '.doxoade', 'vulcan', 'bin')
    if os.path.exists(vulcan_bin) and vulcan_bin not in sys.path:
        sys.path.insert(0, vulcan_bin)

    _exit_code = 0
    try:
        cli(obj={})
    except KeyboardInterrupt:
        click.secho('\n[!] Operação cancelada pelo usuário.', fg='yellow')
        _exit_code = 130
    except SystemExit as se:
        _exit_code = se.code if isinstance(se.code, int) else (1 if se.code else 0)
        if _exit_code not in (0, 130):
            from doxoade.rescue import activate_protocol
            error_data = traceback.format_exc()
            if "NoneType" in error_data or not error_data.strip():
                error_data = f"SystemExit: O comando encerrou prematuramente com código {_exit_code}"
            activate_protocol(error_data, exit_code=_exit_code)
        sys.exit(_exit_code)
    except Exception:
        from doxoade.rescue import activate_protocol
        activate_protocol(traceback.format_exc())
        sys.exit(1)
    finally:
        from doxoade.tools.db_utils import stop_persistence_worker
        stop_persistence_worker()


if __name__ == '__main__':
    main()