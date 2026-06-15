# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/macrothon_executor.py
import os, sys, re, time, click, shutil, asyncio, inspect, builtins, importlib.util
from pathlib import Path
from doxoade.database import get_db_connection
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from doxoade.tools.telemetry_tools.logger import ExecutionLogger, chief_heartbeat
from doxoade.commands.init import _refactor_to_silo
from .macrothon_translator import MacrothonTranslator
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec

_MACRO_LOOP = asyncio.new_event_loop()

class MacrothonRuntime:
    def __init__(self, house_path):
        self.house_path = Path(house_path).resolve()
        self.loaded_bricks = {}
        self.context = self._init_sandbox_context()

    def _init_sandbox_context(self):
        def smart_call(func, *args):
            actual = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args
            if inspect.iscoroutinefunction(func): 
                return _MACRO_LOOP.run_until_complete(func(*actual))
            return func(*actual)
        return {
            'print': print, 'str': str, 'list': list, 'len': len, 'range': range,
            'Fore': Fore, 'Style': Style, 'time': time, 'inspect': inspect,
            '__builtins__': builtins.__dict__, '_MACRO_METRICS': [], '_CALL': smart_call
        }

    def _sync_infra(self, raw_content):
        """Sincroniza TREE e IMPORT."""
        # 1. TREE Sync
        tree_match = re.search(r"TREE\s*\{(.*?)\}", raw_content, re.DOTALL)
        if tree_match:
            for ln in tree_match.group(1).strip().splitlines():
                ln = ln.split('#')[0].strip()
                if not ln: continue
                if ln.endswith('/'): (Path(ln.rstrip('/'))).mkdir(parents=True, exist_ok=True)
                else: self._provision_brick(ln, Path("bricks"))

        # 2. IMPORT Sync
        import_match = re.search(r"IMPORT\s*\{(.*?)\}", raw_content, re.DOTALL)
        if import_match:
            for ln in import_match.group(1).splitlines():
                ln = ln.split('#')[0].strip()
                if not ln: continue
                if ln.startswith(("import ", "from ")):
                    try: restricted_safe_exec(ln, self.context)
                    except Exception as e:
                        import sys as _dox_sys, os as _dox_os
                        from traceback import print_tb as exc_trace
                        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        line_n = exc_tb.tb_lineno
                        exc_trace(exc_tb)
                        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _sync_infra\033[0m")
                        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                    continue
                m = re.match(r"acervo\s+([\w\d_]+)\s*:\s*([\w\d_]+)\s+as\s+([\w\d_]+)", ln)
                if m:
                    mod, func, alias = m.groups()
                    self._bind_brick(mod, func, alias)

    def _provision_brick(self, name, target_dir):
        conn = get_db_connection()
        row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name=?", (name,)).fetchone()
        conn.close()
        if row:
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / f"{name}.py"
            from doxoade.commands.moduloid_systems.moduloid_acervo import BRICKS_DIR
            shutil.copy2(BRICKS_DIR / row[0], dst)
            dst.write_text(_refactor_to_silo(dst.read_text(encoding='utf-8', errors='ignore')), encoding='utf-8')
            return dst
        return None

    def _bind_brick(self, mod_name, func_name, alias):
        if mod_name not in self.loaded_bricks:
            files = list(Path(".").rglob(f"{mod_name}.py"))
            target = files[0] if files else self._provision_brick(mod_name, Path("bricks"))
            if target:
                spec = importlib.util.spec_from_file_location(mod_name, str(target))
                m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
                self.loaded_bricks[mod_name] = m
        if mod_name in self.loaded_bricks:
            self.context[alias] = getattr(self.loaded_bricks[mod_name], func_name)
            click.echo(f"   {Fore.GREEN}●{Style.RESET_ALL} Função '{alias}' vinculada.")

    def run(self):
        abs_root = str(self.house_path).replace("\\", "/")
        old_cwd = os.getcwd()
        os.chdir(abs_root)

        blueprint_file = Path(f"{self.house_path.name.replace('_house', '')}.macrothon")
        if not blueprint_file.exists(): blueprint_file = Path("main.macrothon")
        
        raw_content = blueprint_file.read_text(encoding='utf-8', errors='ignore')
        self._sync_infra(raw_content)
        
        translator = MacrothonTranslator(raw_content)
        code_final = translator.translate(self.context.keys())

        if translator.orphaned_blocks:
            from doxoade.rescue import activate_protocol
            activate_protocol(f"MacrothonArchitectureError: Bloco '{translator.orphaned_blocks[0][0]}' sem IMPORT.")
            return

        self._check_metalcraft_sync()
        (Path("logs") / "shadow_exec.py").write_text(code_final, encoding='utf-8')

        try:
            header = f"import os, sys; os.chdir(r'{abs_root}'); print(f'   {{Fore.GREEN}}✔ Maquinário Ancorado em: {{os.getcwd()}}{{Style.RESET_ALL}}'); sys.stdout.flush()\n"
            with ExecutionLogger('macrothon-run', abs_root, {"house": self.house_path.name}) as logger:
                restricted_safe_exec(header + code_final, self.context, allow_imports=True)
                perf = self.context.get('_MACRO_METRICS', [])
                chief_heartbeat("MACROTHON", "HOUSE_FINISHED", {"house": self.house_path.name, "blocks": perf})
            click.secho(f"✔ House concluída.", fg="green")
        except Exception:
            from doxoade.rescue import activate_protocol
            import traceback; activate_protocol(traceback.format_exc())
        finally: os.chdir(old_cwd)

    def _check_metalcraft_sync(self):
        prefix = self.house_path.name.replace("_house", "")
        toml_path = Path(f"{prefix}_metalcraft.toml")
        if not toml_path.exists(): return
        import toml
        config = toml.load(open(toml_path, 'r', encoding='utf-8', errors='ignore'))
        for src_rel in config.get('build', {}).get('targets', []):
            src = Path(src_rel)
            bin_p = src.with_suffix(".dll" if os.name == 'nt' else ".so")
            if not bin_p.exists() or src.stat().st_mtime > bin_p.stat().st_mtime:
                click.secho(f"   ⚒️  [METALCRAFT] Re-forjando {src.name}...", fg="yellow")
                cmd = f"gcc -shared -O3 -o \"{bin_p}\" \"{src}\""
                res = __import__('subprocess').run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode != 0: click.secho(f"      ✘ Falha: {res.stderr}", fg="red")