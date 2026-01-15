# -*- coding: utf-8 -*-
"""
Rescue System - Lazarus Protocol v41.7.
Forensic UI, emergency recovery and state reversion.
Compliance: MPoT-4, MPoT-5, PASC-6, Aegis Protocol.
"""

import sys
import os
import json
import sqlite3
import hashlib
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# PASC-6.1: Verbose Imports (Aegis Security)
from subprocess import run as sub_run, Popen as sub_popen # nosec
from shutil import which as find_executable
from colorama import init, Fore, Style

# Initialize colorama for this module's scope
init(autoreset=True)

__all__ = ['activate_protocol', 'analyze_crash']

def run_git_command(args: list) -> Optional[str]:
    """Executes git commands with UTF-8 enforcement (Aegis)."""
    if not args:
        return None
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = sub_run(
            ['git'] + args,
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', env=env, shell=False # nosec
        )
        return result.stdout.strip()
    except Exception as e:
        logging.debug(f"Git command failed: {e}")
        return None

def analyze_crash(traceback_text: str) -> Dict[str, Any]:
    """Extracts forensic metadata from traceback (MPoT-5)."""
    if not traceback_text:
        raise ValueError("Lazarus Failure: Traceback text is required.")

    lines = traceback_text.splitlines()
    crash_info = {'file': None, 'line': None, 'error': lines[-1] if lines else "Unknown Error"}

    for line in reversed(lines):
        if 'File "' in line and 'doxoade' in line:
            parts = line.split('"')
            if len(parts) >= 2:
                crash_info['file'] = parts[1]
                try:
                    line_part = line.split('line ')[1].split(',')[0]
                    crash_info['line'] = int(line_part)
                except (IndexError, ValueError):
                    pass
            break
    return crash_info

def get_code_context(filepath: str, linenum: int, source_type: str = "local") -> Optional[str]:
    """
    Retrieves code context (PASC-1.1).
    Restores the 'lost' git context functionality.
    """
    if not filepath or not os.path.exists(filepath):
        return None
        
    try:
        if source_type == "git":
            rel_path = os.path.relpath(filepath, os.getcwd()).replace('\\', '/')
            content = run_git_command(['show', f'HEAD:{rel_path}'])
        else:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        if not content:
            return None
            
        lines = content.splitlines()
        start = max(0, linenum - 3)
        end = min(len(lines), linenum + 2)

        context_str = ""
        for i in range(start, end):
            is_target = (i == linenum - 1)
            marker = " >> " if is_target else "    "
            # Vermelho para o erro atual, Verde para o estado estável do Git
            color = Fore.RED if (is_target and source_type == "local") else (Fore.GREEN if is_target else "")
            context_str += f"{color}{marker}{i+1:4} | {lines[i]}{Style.RESET_ALL}\n"
            
        return context_str.rstrip()
    except Exception as e:
        logging.error(f"Context retrieval failed ({source_type}): {e}")
        return None

def perform_post_mortem(info: Dict[str, Any]):
    """Collects forensic data and persists to DB (MPoT-5)."""
    if not info or not info.get('file'):
        raise ValueError("Invalid crash info for autopsy.")

    print(f"\n{Fore.CYAN}[DOXOADE] 🔬 Performing digital autopsy...")
    
    rel_path = os.path.relpath(info['file'], os.getcwd()).replace('\\', '/')
    stable_content = run_git_command(['show', f'HEAD:{rel_path}'])
    
    if not stable_content:
        print(f"{Fore.YELLOW}   > [WARNING] Stable version unreachable.{Style.RESET_ALL}")
        return

    unique_str = f"{info['error']}:{info['line']}:{rel_path}"
    crash_hash = hashlib.sha256(unique_str.encode('utf-8')).hexdigest()
    _save_crash_to_db(crash_hash, stable_content, rel_path, info)

def _save_crash_to_db(crash_hash: str, content: str, rel_path: str, info: dict):
    """Internal DB persistence for Genesis engine (MPoT-17)."""
    db_path = Path.home() / '.doxoade' / 'doxoade.db'
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO solutions "
                       "(finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (crash_hash, content, "RESCUE_REVERT", os.getcwd(),
                        datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        rel_path, f"[CRASH] {info['error']}", info['line']))
        conn.commit()
        conn.close()
        print(f"   {Fore.GREEN}> [MEMORY] Incident recorded for Genesis.{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"Autopsy DB write failed: {e}")

def activate_protocol(error_text: str):
    """Main entry point for Lazarus Protocol (PASC-10)."""
    if error_text is None:
        raise ValueError("activate_protocol: str 'error_text' não pode ser None.")
    if not error_text:
        return
    
    print("\n" + Fore.RED + Style.BRIGHT + "!"*60)
    print("   [FATAL SYSTEM CRASH DETECTED]")
    print("!"*60 + Style.RESET_ALL)
    
    info = analyze_crash(error_text)
    
    if info['file']:
        _render_dual_forensic_report(info)

    print(f"\n{Fore.WHITE}{Style.BRIGHT}--- RESCUE OPTIONS ---{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}1.{Style.RESET_ALL} [GIT] Revert file to {Fore.GREEN}STABLE{Style.RESET_ALL} version.")
    print(f"{Fore.YELLOW}2.{Style.RESET_ALL} [EDIT] Open editor to fix manually.")
    print(f"{Fore.YELLOW}3.{Style.RESET_ALL} [INFO] View full traceback.")

    _handle_user_choice(input(f"\n{Fore.CYAN}Choice (1-3): {Style.RESET_ALL}").strip(), info, error_text)

def _render_dual_forensic_report(info: dict):
    """Renders visual contrast between broken and stable code (Chief-Gold UI)."""
    if info is None:
        raise ValueError("_render_dual_forensic_report: dict 'info' não pode ser None.")
    print(f"{Fore.RED}{Style.BRIGHT}REASON: {info['error']}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}LOC:    {info['file']}:{info['line']}{Style.RESET_ALL}")

    # 1. Broken Context (Local)
    print(f"\n{Fore.RED}{Style.BRIGHT}--- BROKEN CONTEXT (Local File) ---{Style.RESET_ALL}")
    local_ctx = get_code_context(info['file'], info['line'], source_type="local")
    print(local_ctx if local_ctx else "   [!] Could not read local file.")

    # 2. Stable Context (Git)
    print(f"\n{Fore.GREEN}{Style.BRIGHT}--- STABLE CONTEXT (Git HEAD) ---{Style.RESET_ALL}")
    git_ctx = get_code_context(info['file'], info['line'], source_type="git")
    print(git_ctx if git_ctx else "   [!] No Git history available.")

def _handle_user_choice(choice: str, info: dict, original_error: str):
    """Executes the chosen rescue action (MPoT-4)."""
    if choice == '1' and info['file']:
        perform_post_mortem(info)
        print(f"{Fore.YELLOW}Reverting {info['file']}...{Style.RESET_ALL}")
        run_git_command(['checkout', info['file']])
        print(f"{Fore.GREEN}Reversion complete.{Style.RESET_ALL}")
        save_crash_memory(info, "REVERTED")
    elif choice == '2' and info['file']:
        _open_best_editor(info['file'], info['line'])
    else:
        print(f"\n{Fore.RED}--- ORIGINAL TRACEBACK ---{Style.RESET_ALL}")
        print(original_error)

def _open_best_editor(filepath: str, line: int):
    """
    Opens the best available editor (PASC-6.5).
    Exhaustive search for Notepad++ on Windows.
    """
    abs_filepath = os.path.abspath(filepath)

    if os.name != 'nt':
        # Linux/Termux Specialist (Assumption: binaries are in PATH)
        for ed in ['micro', 'nano', 'vim', 'vi']:
            if find_executable(ed):
                args = [abs_filepath + f":{line}"] if ed == 'micro' else [f"+{line}", abs_filepath]
                sub_run([ed] + args, shell=False) # nosec
                return
    else:
        # Windows Specialist - Exhaustive Search Pattern
        # 1. Lista de locais prováveis (Hardcoded + PATH)
        npp_candidates = [
            find_executable("notepad++"),
            find_executable("notepad++.exe"),
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe"
        ]
        
        # 2. Filtra o primeiro que realmente existe no disco
        npp_bin = next((p for p in npp_candidates if p and os.path.exists(p)), None)

        if npp_bin:
            # -n: vai para a linha específica
            # -nosession: evita carregar arquivos antigos
            sub_popen([npp_bin, "-n" + str(line), "-nosession", abs_filepath], shell=False) # nosec
            print(f"   > [INFO] Opening Notepad++ at line {line}...")
            return
            
        # 3. Fallback para o Notepad básico do Windows
        print(f"{Fore.YELLOW}   > [AVISO] Notepad++ não encontrado. Usando Notepad padrão.")
        sub_popen(["notepad.exe", abs_filepath], shell=False) # nosec

def save_crash_memory(info: dict, action: str):
    """Saves a local JSON crash report."""
    cache_dir = Path(os.getcwd()) / '.doxoade_cache'
    cache_dir.mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "file": info['file'], "error": info['error'], "action_taken": action
    }
    try:
        with open(cache_dir / 'fatal_crash_report.json', 'w') as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        logging.error(f"Crash report save failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as _f:
                activate_protocol(_f.read())
        except Exception as _e:
            logging.error(f"Rescue system entry failure: {_e}")
            
# Reciclado
def get_git_context(filepath, linenum): # noqa - esta função é recuperada para reciclagem
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
