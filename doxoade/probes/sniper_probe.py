# doxoade/doxoade/probes/sniper_probe.py
import sys
import os
import runpy
import shlex
import linecache
from doxoade.tools.doxcolors import Fore, Style

class SniperLens:
    def __init__(self, watch_list, project_root):
        self.targets = [t.strip() for t in watch_list.split(',')]
        self.project_root = os.path.normpath(project_root)
        self.colors = [Fore.CYAN, Fore.MAGENTA, Fore.YELLOW, Fore.GREEN, Fore.PRIMARY]
        self.noise_files = {'runtime.py', 'bootstrap.py', 'meta_finder.py', 'abc.py', 'importlib'}

    def tracer(self, frame, event, arg):
        if event != 'line': return self.tracer
        
        filename = frame.f_code.co_filename
        f_base = os.path.basename(filename)
        
        if f_base in self.noise_files and f_base not in self.targets:
            return self.tracer
        
        active_target = None
        for i, t in enumerate(self.targets):
            if t in filename:
                active_target = t
                color = self.colors[i % len(self.colors)]
                break
        
        if not active_target: return self.tracer

        lineno = frame.f_lineno
        line = linecache.getline(filename, lineno).strip()
        
        if line:
            v = frame.f_locals
            meta = ""
            # Feedback de progresso (O que o usuário quer ver)
            if 'article' in v and isinstance(v['article'], dict):
                meta = f" {Fore.GREEN}➔ [TITLE: {v['article'].get('title', '...')[:20]}]{Style.RESET_ALL}"
            elif 'count' in v:
                meta = f" {Fore.YELLOW}[TOTAL: {v['count']}]{Style.RESET_ALL}"

            # [CHIEF-GOLD] Uso de os.write para evitar reentrancy call
            output = f"{color}{f_base:<18}{Style.RESET_ALL} │ {Fore.YELLOW}{lineno:03d}{Style.RESET_ALL} │ {line}{meta}\n"
            os.write(1, output.encode('utf-8', 'ignore'))

        return self.tracer


def run_sniping(script_path, watch_list, args_str=None):
    script_abs = os.path.abspath(script_path)
    project_root = os.path.dirname(script_abs)

    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.chdir(project_root)

    sys.argv = [script_abs]
    if args_str:
        sys.argv.extend(shlex.split(args_str))
    
    lens = SniperLens(watch_list, project_root)
    sys.settrace(lens.tracer)
    
    print(f"\x1b[94m[*] Sniper Lens ativo em: {watch_list}\x1b[0m")
    
    try:
        runpy.run_path(script_abs, run_name='__main__')
    except SystemExit: pass
    except Exception as e:
        print(f"\n\x1b[31m[!] CRASH NA VIGILÂNCIA: {e}\x1b[0m")
    finally:
        sys.settrace(None)