# doxoade/rescue.py
import sys
import os
import subprocess
import json
import datetime

def run_git_command(args):
    """Executa git sem depender do shared_tools."""
    try:
        # Força encoding utf-8 para evitar problemas de charmap no Windows
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            ['git'] + args, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace',
            env=env
        )
        return result.stdout.strip()
    except Exception:
        return None

def analyze_crash(traceback_text):
    """Mineração de traceback simplificada e independente."""
    lines = traceback_text.splitlines()
    crash_info = {'file': None, 'line': None, 'error': None}
    
    if lines:
        crash_info['error'] = lines[-1]

    for line in reversed(lines):
        if 'File "' in line and 'doxoade' in line:
            parts = line.split('"')
            if len(parts) >= 2:
                crash_info['file'] = parts[1]
                try:
                    line_part = line.split('line ')[1].split(',')[0]
                    crash_info['line'] = int(line_part)
                except: pass
            break
            
    return crash_info

def get_git_context(filepath, linenum):
    """
    Recupera o contexto 'estável' (HEAD) do arquivo via Git.
    Isso mostra como o código era antes de quebrar.
    """
    try:
        # Normaliza caminho para o Git (sempre forward slash)
        rel_path = os.path.relpath(filepath, os.getcwd()).replace('\\', '/')
        
        content_old = run_git_command(['show', f'HEAD:{rel_path}'])
        if not content_old: return None
        
        lines = content_old.splitlines()
        total_lines = len(lines)
        
        # Pega 1 linha antes e 1 depois para contexto
        start = max(0, linenum - 2)
        end = min(total_lines, linenum + 1)
        
        context_str = ""
        for i in range(start, end):
            prefix = ">>" if i == (linenum - 1) else "  "
            context_str += f"   {prefix} {i+1:4}: {lines[i]}\n"
            
        return context_str.rstrip()
    except Exception:
        return None

def activate_protocol(error_text):
    print("\n" + "!"*60)
    print("   [CRASH FATAL DO SISTEMA DETECTADO]")
    print("   O Doxoade encontrou um erro irrecuperável e não pode iniciar.")
    print("!"*60 + "\n")
    
    info = analyze_crash(error_text)
    
    print(f"MOTIVO: {info['error']}")
    if info['file']:
        print(f"LOCAL:  {info['file']}:{info['line']}")
        
        # --- NOVO: ANÁLISE COMPARATIVA (Smart Suggestion) ---
        print("\n--- ANÁLISE FORENSE (O que mudou?) ---")
        
        # 1. Pega linha atual (Quebrada)
        try:
            with open(info['file'], 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if 0 <= info['line'] - 1 < len(lines):
                    bad_line = lines[info['line'] - 1].strip()
                    print(f"[ATUAL/ERRO]  : {bad_line}")
                else:
                    print(f"[ATUAL/ERRO]  : (Linha {info['line']} não acessível)")
        except: pass

        # 2. Pega versão estável do Git
        git_context = get_git_context(info['file'], info['line'])
        if git_context:
            print(f"[GIT/ESTÁVEL] :\n{git_context}")
            print("\nSUGESTÃO: Compare a versão [ATUAL] com a [ESTÁVEL] acima.")
        else:
            print("[GIT] Não foi possível ler a versão anterior (arquivo novo ou não rastreado).")
        # ----------------------------------------------------
    
    print("\n--- OPÇÕES DE RESGATE ---")
    print("1. [GIT] Reverter arquivo para a versão ESTÁVEL.")
    print("2. [EDIT] Abrir no Notepad++ para corrigir.")
    print("3. [INFO] Ver traceback completo.")
    
    choice = input("\nEscolha (1-3): ").strip()
    
    if choice == '1' and info['file']:
        print(f"Revertendo {info['file']}...")
        run_git_command(['checkout', info['file']])
        print("Arquivo revertido com sucesso.")
        save_crash_memory(info, "REVERTED")

    elif choice == '2' and info['file']:
        npp_paths = [
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe"
        ]
        opened = False
        for npp in npp_paths:
            if os.path.exists(npp):
                subprocess.Popen([npp, info['file'], f"-n{info['line']}"])
                opened = True
                break
        if not opened:
            subprocess.Popen(["notepad", info['file']])

    else:
        print("\n--- TRACEBACK ORIGINAL ---")
        print(error_text)

def save_crash_memory(info, action):
    """Salva o incidente para aprendizado."""
    cache_dir = os.path.join(os.getcwd(), '.doxoade_cache')
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    
    report = {
        "timestamp": str(datetime.datetime.now()),
        "type": "FATAL_CRASH",
        "file": info['file'],
        "error": info['error'],
        "action_taken": action
    }
    
    with open(os.path.join(cache_dir, 'fatal_crash_report.json'), 'w') as f:
        json.dump(report, f)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
            err = f.read()
        activate_protocol(err)