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
from pathlib import Path
# [DOX-UNUSED] import traceback
from importlib import import_module

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.doxcolors import init as init_colors
from doxoade.tools.command_metadata import COMMAND_META, format_help

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
            'horus': 'doxoade.commands.horus_cmd:horus_group',
            'ide': 'doxoade.commands.mobile_ide:ide', 
            'impact-analysis': 'doxoade.commands.impact_analysis:impact_analysis', 
            'init': 'doxoade.commands.init:init', 
            'install': 'doxoade.commands.install:install', 
            'intelligence': 'doxoade.commands.intelligence:intelligence', 
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
            'moddify': 'doxoade.commands.moddify:moddify', 
            'moduloid': 'doxoade.commands.moduloid_systems.moduloid_acervo:moduloid_group',
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
            'termux-config': 'doxoade.commands.termux_command:termux_config', 
            'test': 'doxoade.commands.test:test', 
            'timeline': 'doxoade.commands.timeline:timeline', 
            'vault': 'doxoade.commands.vault_cmd:vault_group',
            'venvkeeper': 'doxoade.commands.venvkeeper_systems.venvkeeper:venvkeeper', 
            'venv': 'doxoade.commands.venv_cmd:venv_cmd',
            'verilog': 'doxoade.commands.verilog:verilog', 
            'vulcan': 'doxoade.commands.vulcan_cmd:vulcan_group', 
            'webcheck': 'doxoade.commands.webcheck:webcheck',
            'wsl': 'doxoade.commands.linux_systems.linux_cmd:linux_group',
            'flow-diag': 'doxoade.diagnostic.flow_necropsy:run_flow_necropsy',
            'test-shadow': 'doxoade.commands.test_shadow:test_shadow',
            'stress-hades': 'doxoade.commands.stress_test:stress_hades',
            'stress-abyss': 'doxoade.commands.stress_test:stress_abyss',
        }

    def _load_cache(self):
        if self._cache_path.exists():
            return json.loads(self._cache_path.read_text())
        return {}

    def _sanitize(self, text: str) -> str:
        import re
        # Remove apenas os parênteses e o que tem dentro (ex: "(doxoade)", "(v85.2)")
        text = re.sub(r'\s*\([^)]*\)', '', text)
        return text.strip()

    def _rebuild_cache(self, force=False):
        import ast
        import os
        
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
                
                # Cores
                color = Fore.CYAN
                if any(x in name for x in ['hack', 'security', 'audit']): color = Fore.RED
                elif any(x in name for x in ['db', 'config', 'venv']): color = Fore.YELLOW
                
                # Coluna fixa de 20 espaços para o nome (já com a cor aplicada)
                colored_name = f"  {color}{name:<20}{Style.RESET_ALL}"
                
                # Quebra de linha inteligente para a descrição não estourar a tela
                # Largura máxima da descrição = 75 caracteres
                wrapped_desc = textwrap.wrap(desc, width=75)
                
                if not wrapped_desc:
                    formatter.write(f"{colored_name}\n")
                else:
                    # Primeira linha com o comando
                    formatter.write(f"{colored_name}{wrapped_desc[0]}\n")
                    # Linhas seguintes alinhadas logo abaixo da descrição
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
        except SyntaxError as e:
            from doxoade.rescue import activate_protocol
            import traceback
            activate_protocol(traceback.format_exc())
            return None
        except Exception: pass

        # --- CARREGAMENTO REAL E INJEÇÃO DE CORES ---
        # --- CARREGAMENTO REAL E INJEÇÃO DE CORES ---
        try:
            mod = import_module(module_path)
            cmd = getattr(mod, attr_name)
            
            # 1. Colore e SANITIZA o Título/Descrição principal do Comando
            import re
            base_help = getattr(cmd, 'help', None) or self._help_cache.get(name, "")
            if base_help:
                # Remove cores antigas e passa pelo nosso removedor de emojis/parênteses!
                clean_help = re.sub(r'\x1b\[[0-9;]*m', '', base_help)
                clean_help = self._sanitize(clean_help)
                cmd.help = f"{Fore.CYAN}{Style.BRIGHT}{clean_help}{Style.RESET_ALL}"

            # 2. Injeta cores dinâmicas nas Flags e Opções
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

            # 3. Subcomandos Coloridos e Imparáveis!
            if isinstance(cmd, click.Group) and not getattr(cmd, '_dox_group_patched', False):
                orig_format_commands = cmd.format_commands
                def patched_format_commands(ctx_inner, formatter):
                    commands = []
                    for sub_name in cmd.list_commands(ctx_inner):
                        sub_cmd = cmd.get_command(ctx_inner, sub_name)
                        if sub_cmd is None: continue
                        
                        # Tenta puxar a descrição de 3 fontes diferentes (Obrigatório para Subcomandos)
                        help_str = getattr(sub_cmd, 'help', None)
                        if not help_str and hasattr(sub_cmd, 'callback'):
                            import inspect
                            help_str = inspect.getdoc(sub_cmd.callback)
                        if not help_str:
                            help_str = "Sem descrição."
                            
                        # Limpa emojis/parênteses e pega a primeira linha
                        help_str = self._sanitize(help_str.split('\n')[0])
                        
                        colored_sub_name = f"{Fore.CYAN}{sub_name}{Style.RESET_ALL}"
                        colored_sub_desc = f"{Style.DIM}{help_str}{Style.RESET_ALL}"
                        commands.append((colored_sub_name, colored_sub_desc))
                        
                    if commands:
                        with formatter.section("Commands"):
                            formatter.write_dl(commands)
                
                cmd.format_commands = patched_format_commands
                cmd._dox_group_patched = True

            return cmd
            
        except Exception as e:
            if not ctx.resilient_parsing:
                from doxoade.rescue import activate_protocol
                import traceback
                activate_protocol(traceback.format_exc(), exit_code=1)
            
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            exc_trace(exc_tb)
            print(f"\033[1;31m\n[ FATAL ] Erro na Matriz de Comando: '{name}'\033[0m")
            print(f"\033[1;34m ■ CAUSA      :\033[0m {e}")
            return None

    def _print_fatal_import(self, cmd_name, e):
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
        
        print(f"\033[1;31m\n[ FATAL ] Erro na Matriz de Comando: '{cmd_name}'\033[0m")
        print("\033[1;34m ■ SUBSISTEMA :\033[0m Intelligence Router")
        print(f"\033[1;34m ■ CAUSA      :\033[0m {e}")
#        print(f"\033[1;34m ■ DIAGNÓSTICO:\033[0m Verifique se o módulo 'telemetry_tools.logger' foi movido.")
#        print(Fore.RED)
#        traceback.print_exc()
#        print(Style.RESET_ALL)

@click.group(cls=DoxoadeLazyGroup, invoke_without_command=True)
@click.option('--guard', is_flag=True, help='Verificação de integridade Aegis.')
@click.option('--refresh-help', is_flag=True, help='Força a atualização do cache de descrições.') # <-- ADICIONE AQUI
@click.pass_context
def cli(ctx, guard, refresh_help): # <-- ADICIONE O ARGUMENTO AQUI
    """olDox222 Advanced Development Environment (doxoade)."""
    
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
    import os
    os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
    # 1. Forçar encoding UTF-8
    if sys.stdout.encoding != 'utf-8':
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            from traceback import print_tb as exc_trace
            exc_obj, exc_tb = _dox_sys.exc_info()
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            exc_trace(exc_tb)
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: main\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    # 2. Injetar o VENV (mesma lógica do __main__)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    # Procura site-packages
    venv_candidates = [
        os.path.join(project_root, 'venv', 'Lib', 'site-packages'),
        os.path.join(project_root, 'venv', 'lib', 'site-packages'), # Linux fallback
    ]
    for venv_path in venv_candidates:
        if os.path.exists(venv_path) and venv_path not in sys.path:
            sys.path.insert(0, venv_path)
            break
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
        
        # --- [VITAL] DISPARO DE EMERGÊNCIA PARA SYSTEM EXIT ---
        if _exit_code not in (0, 130):
            from doxoade.rescue import activate_protocol
            # Tenta pegar o rastro, se não houver, envia o código
            import traceback
            error_data = traceback.format_exc()
            if "NoneType" in error_data or not error_data.strip():
                error_data = f"SystemExit: O comando encerrou prematuramente com código {_exit_code}"
            
            activate_protocol(error_data, exit_code=_exit_code)
        
        sys.exit(_exit_code)
    except Exception as e:
        from doxoade.rescue import activate_protocol
        error_data = traceback.format_exc()
        activate_protocol(error_data)
        sys.exit(1)
    finally:
        from doxoade.tools.db_utils import stop_persistence_worker
        stop_persistence_worker()
if __name__ == '__main__':
    main()
