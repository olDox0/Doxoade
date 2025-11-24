# doxoade/probes/flow_runner.py
import sys
import os
import time
import linecache
from colorama import init, Fore, Style, Back

# Força UTF-8 no stdout para Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

init(autoreset=True)

class FlowTracer:
    def __init__(self, target_script):
        # ... (código igual ao anterior) ...
        self.target_script = os.path.normcase(os.path.abspath(target_script))
        self.last_time = time.perf_counter()
        self.last_locals = {}
        
        self.SLOW = 0.1
        self.CRITICAL = 1.0

        self.python_dir = os.path.normcase(os.path.dirname(sys.executable))
        self.cwd = os.getcwd()
        self.target_name = os.path.basename(self.target_script) # Pega o nome do script
        
        # SEPARADOR VISUAL SEGURO
        # Tenta usar o caractere bonito, mas se o terminal não suportar, usa pipe normal
        try:
            self.sep_char = "│"
            print(" " + self.sep_char + " ", end="\r") # Teste silencioso
        except UnicodeEncodeError:
            self.sep_char = "|"

    def trace_calls(self, frame, event, arg):
        # ... (código de filtro igual ao anterior) ...
        if event != 'line':
            return self.trace_calls
        
        code_path = frame.f_code.co_filename
        if code_path.startswith('<'): return self.trace_calls
        
        abs_path = os.path.normcase(os.path.abspath(code_path))
        
        # Se estamos rodando o 'command_wrapper.py', QUEREMOS ver o código do 'doxoade'
        is_meta_analysis = 'command_wrapper.py' in self.target_name
        
        if 'flow_runner.py' in abs_path: return self.trace_calls
        
        # Se NÃO for meta-análise, aplica o filtro antigo
        if not is_meta_analysis:
             if os.sep + 'doxoade' + os.sep in abs_path: return self.trace_calls
        
        is_in_cwd = abs_path.startswith(os.path.normcase(self.cwd))
        if not is_in_cwd: return self.trace_calls
        if 'site-packages' in abs_path or os.sep + 'lib' + os.sep in abs_path: return self.trace_calls

        # ... (cálculo de tempo igual) ...
        current_time = time.perf_counter()
        delta = current_time - self.last_time
        self.last_time = current_time
        
        if delta > self.CRITICAL:
            t_color = Fore.WHITE + Back.RED + Style.BRIGHT
        elif delta > self.SLOW:
            t_color = Fore.BLACK + Back.YELLOW
        else:
            t_color = Fore.CYAN + Style.DIM

        time_str = f"{delta:.4f}s"

        # ... (display e variáveis) ...
        lineno = frame.f_lineno
        filename = os.path.basename(code_path)
        line_content = linecache.getline(code_path, lineno).strip()
        if len(filename) > 15: filename = filename[:12] + "..."

        current_locals = frame.f_locals.copy()
        changes = []
        for name, val in current_locals.items():
            if name.startswith('__'): continue
            if name not in self.last_locals or self.last_locals[name] != val:
                try: 
                    # Mudei o nome da variável aqui para bater com o uso abaixo
                    v_str = repr(val) 
                except: 
                    v_str = "<obj>"
                
                if len(v_str) > 30: v_str = v_str[:27] + "..."
                
                # Agora v_str existe e está correto
                changes.append(f"{Fore.GREEN}{name}{Fore.WHITE}={Style.DIM}{v_str}")
        
        self.last_locals = current_locals

        # LAYOUT CORRIGIDO COM CARACTERE SEGURO
        col_time = f"{t_color} {time_str} {Style.RESET_ALL}"
        col_loc = f"{Fore.BLUE}{filename}:{Fore.WHITE}{lineno:<4}"
        col_code = f"{Fore.WHITE}{line_content:<50}"
        
        sep = f"{Fore.BLACK + Style.BRIGHT}{self.sep_char}{Style.RESET_ALL}"
        
        output = f"{col_time} {sep} {col_loc} {sep} {col_code}"
        
        if changes:
            output += f" {sep} {' '.join(changes)}"
            
        print(output)
        return self.trace_calls

# ... (resto do arquivo run_flow igual) ...
def run_flow(script_path):
    abs_script_path = os.path.abspath(script_path)
    print(Fore.MAGENTA + Style.BRIGHT + "="*100)
    print(Fore.MAGENTA + Style.BRIGHT + f" DOXOADE FLOW v1.0 | Rastreando: {os.path.basename(script_path)}")
    print(Fore.WHITE + Style.DIM + f" Performance: {Back.RED} >1.0s {Style.RESET_ALL} {Back.YELLOW}{Fore.BLACK} >0.1s {Style.RESET_ALL}")
    print(Fore.MAGENTA + Style.BRIGHT + "="*100)
    
    tracer = FlowTracer(abs_script_path)
    sys.settrace(tracer.trace_calls)
    sys.path.insert(0, os.path.dirname(abs_script_path))
    
#    original_argv = sys.argv
#    sys.argv = [abs_script_path] + sys.argv[2:]
    
    try:
        with open(abs_script_path, 'rb') as f:
            code = compile(f.read(), abs_script_path, 'exec')
            globs = {
                '__name__': '__main__',
                '__file__': abs_script_path,
            }
            exec(code, globs)
    except Exception as e:
        sys.settrace(None)
        print(Fore.RED + "-"*100)
        print(Fore.RED + Style.BRIGHT + "[FLOW CRASH] O script falhou.")
        raise e
    finally:
        sys.settrace(None)
        print(Fore.GREEN + "-"*100)
        print(Fore.GREEN + "[FLOW] Finalizado.")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    run_flow(sys.argv[1])