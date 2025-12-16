# doxoade/rescue.py
import sys
import os
import subprocess
import json
import datetime
import sqlite3
import hashlib
import traceback
from pathlib import Path

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
    finally: print("." ,end="",flush=True)

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
                except Exception: pass
                finally: print("." ,end="",flush=True)
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
    finally: print("." ,end="",flush=True)

def perform_post_mortem(info):
    """
    (NOVO) Realiza a autópsia do erro antes de reverter.
    Salva o estado 'Quebrado' vs 'Estável' no banco de dados para aprendizado futuro.
    """
    print("\n[DOXOADE] 🔬 Realizando autópsia digital...")
    file_path = info['file']
    if not file_path or not os.path.exists(file_path):
        return

    try:
        # 1. Captura o conteúdo 'Quebrado' (Atual)
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            broken_content = f.read()

        # 2. Captura o conteúdo 'Estável' (Git)
        rel_path = os.path.relpath(file_path, os.getcwd()).replace('\\', '/')
        stable_content = run_git_command(['show', f'HEAD:{rel_path}'])
        
        if not stable_content:
            print("   > [AVISO] Não foi possível recuperar versão do Git para comparação.")
            return

        # 3. Gera um Hash único para esse crash
        # Hash = ErrorMsg + Line + File
        unique_str = f"{info['error']}:{info['line']}:{rel_path}"
        crash_hash = hashlib.sha256(unique_str.encode('utf-8')).hexdigest()

        # 4. Salva no Banco de Dados
        # Usamos a tabela 'solutions' pois efetivamente estamos dizendo:
        # "Para este erro (crash_hash), a solução é o conteúdo estável."
        db_path = Path.home() / '.doxoade' / 'doxoade.db'
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Garante que a tabela existe (caso o rescue rode num ambiente muito novo/velho)
        # (A estrutura deve bater com database.py v8+)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, finding_hash TEXT NOT NULL UNIQUE,
                stable_content TEXT NOT NULL, commit_hash TEXT NOT NULL, project_path TEXT NOT NULL,
                timestamp TEXT NOT NULL, file_path TEXT NOT NULL, message TEXT, error_line INTEGER
            );
        """)

        cursor.execute("""
            INSERT OR REPLACE INTO solutions 
            (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            crash_hash,
            stable_content,
            "RESCUE_REVERT", # Marca especial indicando que foi um rescue
            os.getcwd(),
            datetime.datetime.utcnow().isoformat(),
            rel_path,
            f"[CRASH] {info['error']}",
            info['line']
        ))
        
        conn.commit()
        conn.close()
        
        print("   > [MEMÓRIA] Incidente gravado. O Gênese aprenderá com este erro.")
        print("   > [INFO] O conteúdo estável foi registrado como a 'Solução' para este Crash.")

    except Exception as e:
        print(f"   > [ERRO AUTÓPSIA] Falha ao gravar dados: {e}")
    finally: print("." ,end="",flush=True)


def activate_protocol(error_text):
    print("\n" + "!"*60)
    print("   [CRASH FATAL DO SISTEMA DETECTADO]")
    print("   O Doxoade encontrou um erro irrecuperável e não pode iniciar.")
    print("!"*60 + "\n")
    
    info = analyze_crash(error_text)
    
    print(f"MOTIVO: {info['error']}")
    if info['file']:
        print(f"LOCAL:  {info['file']}:{info['line']}")
        
        # --- ANÁLISE COMPARATIVA (Smart Suggestion) ---
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
        except Exception: print(traceback.format_exc())
        finally: print("." ,end="",flush=True)

        # 2. Pega versão estável do Git
        git_context = get_git_context(info['file'], info['line'])
        if git_context:
            print(f"[GIT/ESTÁVEL] :\n{git_context}")
            print("\nSUGESTÃO: Compare a versão [ATUAL] com a [ESTÁVEL] acima.")
        else:
            print("[GIT] Não foi possível ler a versão anterior (arquivo novo ou não rastreado).")
        # ----------------------------------------------------
    
    print("\n--- OPÇÕES DE RESGATE ---")
    print("1. [GIT] Reverter arquivo para a versão ESTÁVEL (e Aprender).")
    print("2. [EDIT] Abrir no Notepad++ para corrigir.")
    print("3. [INFO] Ver traceback completo.")
    
    choice = input("\nEscolha (1-3): ").strip()
    
    if choice == '1' and info['file']:
        # CHAMA A AUTÓPSIA ANTES DE REVERTER
        perform_post_mortem(info)
        
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
    """Salva um log simples JSON local (backup)."""
    cache_dir = os.path.join(os.getcwd(), '.doxoade_cache')
    if not os.path.exists(cache_dir): 
        try: os.makedirs(cache_dir)
        except Exception: print(traceback.format_exc())
        finally: print("." ,end="",flush=True)
    
    report = {
        "timestamp": str(datetime.datetime.now()),
        "type": "FATAL_CRASH",
        "file": info['file'],
        "error": info['error'],
        "action_taken": action
    }
    
    try:
        with open(os.path.join(cache_dir, 'fatal_crash_report.json'), 'w') as f:
            json.dump(report, f)
    except Exception: print(traceback.format_exc())
    finally: print("." ,end="",flush=True)
if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
            err = f.read()
        activate_protocol(err)