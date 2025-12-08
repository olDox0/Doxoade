# doxoade/probes/flow_runner.py
import sys
import os
import time
import inspect
import datetime
import json

class FlowTracer:
    def __init__(self):
        self.last_time = time.perf_counter()
        self.last_locals = {}
        # Cores ANSI
        self.CYAN = '\033[96m'
        self.YELLOW = '\033[93m'
        self.GREEN = '\033[92m'
        self.RED = '\033[91m'
        self.RESET = '\033[0m'
        self.DIM = '\033[2m'
        
        # Configuração de Layout
        self.col_time = 10
        self.col_loc = 20
        self.col_code = 50
        self.col_vars = 40
        
        # Símbolo separador
        self.sep_char = "|"
        try:
            if sys.stdout.encoding and sys.stdout.encoding.lower().startswith('utf'):
                self.sep_char = "│"
        except: pass

        self._print_header()

    def _print_header(self):
        width = self.col_time + self.col_loc + self.col_code + self.col_vars
        print("=" * width)
        print(f" DOXOADE FLOW v1.2 | Rastreando: {sys.argv[0]}")
        print(f" Performance:  {self.RED}>1.0s{self.RESET}   {self.YELLOW}>0.1s{self.RESET}")
        print("=" * width)

    def _safe_compare_changed(self, old_val, new_val):
        """Compara valores de forma segura (suporte a NumPy/Pandas)."""
        try:
            is_diff = (old_val != new_val)
            if hasattr(is_diff, 'any'): # Para arrays numpy
                return is_diff.any()
            return bool(is_diff)
        except:
            return True

    def trace_calls(self, frame, event, arg):
        if event != 'line':
            return self.trace_calls
            
        code = frame.f_code
        filename = code.co_filename
        fname_lower = filename.lower()
        
        # --- FILTROS DE RUÍDO APRIMORADOS ---
        # 1. Ignora o próprio Doxoade
        if "doxoade" in fname_lower and "probes" in fname_lower: return self.trace_calls
        
        # 2. Ignora arquivos que não são Python
        if not filename.endswith(".py"): return self.trace_calls
        
        # 3. Ignora bibliotecas padrão e site-packages (reduz ruído de imports como numpy)
        # No Windows, bibliotecas padrão ficam em Lib\ (ex: Lib\enum.py)
        # Bibliotecas externas ficam em Lib\site-packages\
        if "site-packages" in fname_lower: return self.trace_calls
        if os.sep + "lib" + os.sep in fname_lower: return self.trace_calls 
        
        # --- FIM DOS FILTROS ---

        current_time = time.perf_counter()
        delta = current_time - self.last_time
        self.last_time = current_time
        
        lineno = frame.f_lineno
        
        # Formata tempo
        t_str = f"{delta:.4f}s"
        if delta > 1.0: t_str = f"{self.RED}{t_str}{self.RESET}"
        elif delta > 0.1: t_str = f"{self.YELLOW}{t_str}{self.RESET}"
        
        # Lê código
        try:
            import linecache
            line_content = linecache.getline(filename, lineno).strip()
        except:
            line_content = "???"

        # Processa variáveis
        curr_locals = frame.f_locals.copy()
        diffs = []
        
        for name, val in curr_locals.items():
            if name.startswith('__'): continue
            
            if name not in self.last_locals or self._safe_compare_changed(self.last_locals.get(name), val):
                # --- PROTEÇÃO CONTRA CRASH DE INSPEÇÃO ---
                try:
                    val_str = str(val)
                except Exception:
                    # Se falhar ao converter pra string (ex: objeto não inicializado), mostra placeholder
                    val_str = "<Unprintable>"
                # -----------------------------------------
                
                val_str = val_str.replace('\n', ' ')
                if len(val_str) > 25: val_str = val_str[:22] + "..."
                diffs.append(f"{name}={val_str}")
        
        self.last_locals = curr_locals
        
        # Formatação Visual
        fname = os.path.basename(filename)
        if len(fname) > 15: fname = fname[:12] + "..."
        loc = f"{fname}:{lineno}"
        
        vars_str = ", ".join(diffs)
        
        sep = f" {self.sep_char} "
        # Ajuste de espaçamento manual para alinhar colunas com cores ANSI
        print(f" {t_str:<19} {sep} {loc:<{self.col_loc}} {sep} {line_content:<{self.col_code}} {sep} {self.DIM}{vars_str}{self.RESET}")
        
        return self.trace_calls

def run_flow(script_path, args):
    tracer = FlowTracer()
    sys.settrace(tracer.trace_calls)
    
    sys.argv = [script_path] + args
    file_dir = os.path.dirname(os.path.abspath(script_path))
    if file_dir not in sys.path:
        sys.path.insert(0, file_dir)
    
    try:
        with open(script_path, 'rb') as f:
            code = compile(f.read(), script_path, 'exec')
            
            globs = {
                '__file__': script_path,
                '__name__': '__main__',
                '__package__': None,
                '__cached__': None,
            }
            
            exec(code, globs) # noqa
    except Exception as e:
        print("\n" + "-" * 80)
        print(f"[FLOW CRASH] O script falhou (Erro do Usuário): {e}")
        print("-" * 80)
        # Não damos raise aqui para não mostrar o traceback do doxoade, apenas do script
    finally:
        sys.settrace(None)
        print("\n[FLOW] Finalizado.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: flow_runner.py <script> [args]")
        sys.exit(1)
    run_flow(sys.argv[1], sys.argv[2:])