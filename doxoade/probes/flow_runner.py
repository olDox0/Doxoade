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
        self.last_filename = ""
        
        # Paleta de Cores (ANSI)
        self.C_RESET = '\033[0m'
        self.C_DIM = '\033[2m'
        self.C_CYAN = '\033[96m'
        self.C_YELLOW = '\033[93m'
        self.C_GREEN = '\033[92m'
        self.C_RED = '\033[91m'
        self.C_MAGENTA = '\033[95m'
        self.C_BLUE = '\033[94m'
        self.C_BOLD = '\033[1m'
        self.C_BORDER = '\033[90m' # Cinza escuro
        self.C_WHITE = '\033[97m'  # Branco brilhante [CORREÇÃO]
        
        # Configuração de Layout (Largura Fixa)
        self.W_TIME = 10
        self.W_LOC = 25
        self.W_CODE = 60
        # Variables pega o resto
        
        self.sep = f"{self.C_BORDER}│{self.C_RESET}"
        self._print_header()

    def _print_header(self):
        # Cabeçalho Estilizado
        line = f"{self.C_BORDER}{'─'*120}{self.C_RESET}"
        print(line)
        print(f"{self.C_CYAN}{self.C_BOLD} DOXOADE FLOW v2.0 (Nexus View){self.C_RESET} | Rastreando: {os.path.basename(sys.argv[0])}")
        print(f" {self.C_DIM}Legenda:{self.C_RESET} {self.C_GREEN}<1ms{self.C_RESET} {self.C_CYAN}<10ms{self.C_RESET} {self.C_YELLOW}>100ms{self.C_RESET} {self.C_RED}>1s (Gargalo){self.C_RESET}")
        
        # Títulos das Colunas
        h_time = "TEMPO".center(self.W_TIME)
        h_loc = "ARQUIVO:LINHA".ljust(self.W_LOC)
        h_code = "CÓDIGO EXECUTADO".ljust(self.W_CODE)
        h_vars = "ESTADO / VARIÁVEIS"
        
        print(f"{self.C_BORDER}┌{'─'*self.W_TIME}┬{'─'*self.W_LOC}┬{'─'*self.W_CODE}┬{'─'*30}{self.C_RESET}")
        print(f"{self.C_BORDER}│{self.C_RESET}{self.C_BOLD}{h_time}{self.C_RESET}{self.sep}{self.C_BOLD} {h_loc}{self.C_RESET}{self.sep}{self.C_BOLD} {h_code}{self.C_RESET}{self.sep}{self.C_BOLD} {h_vars}{self.C_RESET}")
        print(f"{self.C_BORDER}├{'─'*self.W_TIME}┼{'─'*self.W_LOC}┼{'─'*self.W_CODE}┼{'─'*30}{self.C_RESET}")

    def _safe_compare_changed(self, old_val, new_val):
        """Compara valores de forma segura (suporte a NumPy/Pandas)."""
        try:
            is_diff = (old_val != new_val)
            if hasattr(is_diff, 'any'): 
                return is_diff.any()
            return bool(is_diff)
        except Exception:
            return True

    def _format_time(self, seconds):
        """Formata o tempo com cor baseada na duração."""
        ms = seconds * 1000
        text = f"{ms:.1f}ms" if ms < 1000 else f"{seconds:.2f}s"
        
        # Padding manual para garantir alinhamento (9 caracteres)
        text = text.rjust(self.W_TIME - 1) + " "

        if seconds > 1.0: return f"{self.C_RED}{self.C_BOLD}{text}{self.C_RESET}"
        if seconds > 0.1: return f"{self.C_YELLOW}{text}{self.C_RESET}"
        if seconds > 0.01: return f"{self.C_CYAN}{text}{self.C_RESET}"
        return f"{self.C_GREEN}{self.C_DIM}{text}{self.C_RESET}"

    def _format_code(self, line):
        """Trunca e coloriza o código."""
        max_len = self.W_CODE - 2
        if len(line) > max_len:
            line = line[:max_len-3] + "..."
        
        # Highlight básico
        line = line.replace("import ", f"{self.C_MAGENTA}import {self.C_RESET}")
        line = line.replace("from ", f"{self.C_MAGENTA}from {self.C_RESET}")
        line = line.replace("def ", f"{self.C_BLUE}def {self.C_RESET}")
        line = line.replace("class ", f"{self.C_BLUE}class {self.C_RESET}")
        line = line.replace("return", f"{self.C_RED}return{self.C_RESET}")
        
        # Preenchimento com espaços para manter a coluna alinhada
        # (Removemos cores para calcular tamanho real, depois recolocamos)
        clean_len = len(line.replace(self.C_MAGENTA, "").replace(self.C_BLUE, "").replace(self.C_RED, "").replace(self.C_RESET, ""))
        padding = " " * (self.W_CODE - clean_len - 1)
        
        return f" {line}{padding}"

    def trace_calls(self, frame, event, arg):
        if event != 'line':
            return self.trace_calls
            
        code = frame.f_code
        filename = code.co_filename
        fname_lower = filename.lower()
        
        # --- FILTROS ---
        if "doxoade" in fname_lower and "probes" in fname_lower: return self.trace_calls
        if not filename.endswith(".py"): return self.trace_calls
        if "site-packages" in fname_lower: return self.trace_calls
        if os.sep + "lib" + os.sep in fname_lower: return self.trace_calls 
        # ---------------

        current_time = time.perf_counter()
        delta = current_time - self.last_time
        self.last_time = current_time
        
        lineno = frame.f_lineno
        
        # --- PREPARAÇÃO DE DADOS ---
        
        # 1. Tempo
        time_str = self._format_time(delta)
        
        # 2. Localização (Arquivo:Linha)
        fname_base = os.path.basename(filename)
        
        # Diminui visualmente se for o mesmo arquivo da linha anterior
        if fname_base == self.last_filename:
            loc_display = f"{self.C_DIM}\" : {lineno:<4}{self.C_RESET}"
        else:
            loc_display = f"{self.C_WHITE}{fname_base}{self.C_DIM}:{lineno}{self.C_RESET}"
            self.last_filename = fname_base
            
        # Garante alinhamento removendo caracteres de escape para cálculo
        clean_loc = f"{fname_base}:{lineno}"
        pad_loc = " " * (self.W_LOC - len(clean_loc) - 1)
        # Se for muito longo, trunca
        if len(clean_loc) > self.W_LOC - 1:
            loc_display = f"{fname_base[:self.W_LOC-5]}...:{lineno}"
            pad_loc = ""
            
        final_loc = f" {loc_display}{pad_loc}"

        # 3. Código
        try:
            import linecache
            line_content = linecache.getline(filename, lineno).strip()
        except Exception:
            line_content = "???"
        
        code_str = self._format_code(line_content)

        # 4. Variáveis (Diff)
        curr_locals = frame.f_locals.copy()
        diffs = []
        for name, val in curr_locals.items():
            if name.startswith('__'): continue
            if name not in self.last_locals or self._safe_compare_changed(self.last_locals.get(name), val):
                try:
                    val_str = str(val)
                except: val_str = "<?>"
                
                val_str = val_str.replace('\n', ' ')
                if len(val_str) > 30: val_str = val_str[:27] + "..."
                
                # Cor para variáveis: Nome (Cyan) = Valor (Amarelo)
                diffs.append(f"{self.C_CYAN}{name}{self.C_DIM}={self.C_YELLOW}{val_str}{self.C_RESET}")
        
        self.last_locals = curr_locals
        vars_str = ", ".join(diffs)
        
        # --- IMPRESSÃO ---
        print(f"{self.C_BORDER}│{self.C_RESET}{time_str}{self.sep}{final_loc}{self.sep}{code_str}{self.sep} {vars_str}")
        
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
    finally:
        sys.settrace(None)
        print(f"\033[90m└{'─'*100}┘\033[0m") # Rodapé da tabela
        print("\n[FLOW] Finalizado.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: flow_runner.py <script> [args]")
        sys.exit(1)
    run_flow(sys.argv[1], sys.argv[2:])