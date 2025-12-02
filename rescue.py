# doxoade/rescue.py
import sys
import os
import subprocess
import json
import datetime

def run_git_command(args):
    """Executa git sem depender do shared_tools."""
    try:
        result = subprocess.run(
            ['git'] + args, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        return result.stdout.strip()
    except Exception:
        return None

def analyze_crash(traceback_text):
    """Mineração de traceback simplificada e independente."""
    lines = traceback_text.splitlines()
    crash_info = {'file': None, 'line': None, 'error': None}
    
    # Pega a última linha (O Erro)
    if lines:
        crash_info['error'] = lines[-1]

    # Procura a última ocorrência de arquivo do projeto (ignorando bibliotecas python)
    for line in reversed(lines):
        if 'File "' in line and 'doxoade' in line:
            # Ex: File "C:\...\doxoade\cli.py", line 50, in <module>
            parts = line.split('"')
            if len(parts) >= 2:
                crash_info['file'] = parts[1]
                # Tenta pegar a linha
                try:
                    line_part = line.split('line ')[1].split(',')[0]
                    crash_info['line'] = int(line_part)
                except: pass
            break
            
    return crash_info

def activate_protocol(error_text):
    print("\n" + "!"*60)
    print("   [CRASH FATAL DO SISTEMA DETECTADO]")
    print("   O Doxoade encontrou um erro irrecuperável e não pode iniciar.")
    print("!"*60 + "\n")
    
    info = analyze_crash(error_text)
    
    print(f"MOTIVO: {info['error']}")
    if info['file']:
        print(f"LOCAL:  {info['file']}:{info['line']}")
    
    print("\n--- OPÇÕES DE RESGATE ---")
    print("1. [GIT] Reverter o arquivo culpado para o último commit (Recomendado).")
    print("2. [EDIT] Abrir o arquivo no Notepad++ para correção manual.")
    print("3. [IGNORAR] Sair e mostrar o traceback completo.")
    
    choice = input("\nEscolha (1-3): ").strip()
    
    if choice == '1' and info['file']:
        print(f"Revertendo {info['file']}...")
        out = run_git_command(['checkout', info['file']])
        print("Arquivo revertido. Tente rodar o doxoade novamente.")
        
        # Salva para o Genesis aprender depois
        save_crash_memory(info, "REVERTED_VIA_RESCUE")

    elif choice == '2' and info['file']:
        # Tenta abrir no notepad++ (Caminho padrão do Windows)
        npp_paths = [
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe"
        ]
        opened = False
        for npp in npp_paths:
            if os.path.exists(npp):
                subprocess.Popen([npp, info['file'], f"-n{info['line']}"])
                print("Arquivo aberto.")
                opened = True
                break
        if not opened:
            # Fallback para o bloco de notas
            subprocess.Popen(["notepad", info['file']])

    else:
        print("\n--- TRACEBACK ORIGINAL ---")
        print(error_text)

def save_crash_memory(info, action):
    """Salva o incidente para que o Gênese aprenda quando o sistema voltar."""
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
    # Este script é chamado pelo __main__.py passando o erro via stdin ou argumento
    if len(sys.argv) > 1:
        # Se passado como arquivo de log de erro
        with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
            err = f.read()
        activate_protocol(err)