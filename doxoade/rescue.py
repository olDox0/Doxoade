# -*- coding: utf-8 -*-
# doxoade/doxoade/rescue.py
"""
Rescue System - Lazarus Protocol v43.0 Platinum Gold.
Agregador Forense: Sotéria (Nativo) + Aegis (Sandbox) + Lazarus (Triangulação).
"""
import sys
import os
import re
import datetime
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from subprocess import Popen as sub_popen
from shutil import which as find_executable

# Importação protegida
try:
    import doxoade.tools.aegis.nexus_db as sqlite3 # noqa
except ImportError:
    sqlite3 = None

from doxoade.tools.doxcolors import Fore, Style, Back

__all__ = ['activate_protocol', 'analyze_crash']

def run_git_command(args: list) -> Optional[str]:
    """Executa comandos git de forma segura."""
    if not args: return None
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(['git'] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, shell=False)
        return result.stdout.strip()
    except Exception: return None

def _open_best_editor(filepath: str, line: int):
    """Abre o Notepad++ no Windows (Gold Standard) ou Micro/Vim no Linux."""
    abs_path = os.path.abspath(filepath)
    if os.name == 'nt':
        # Localização exaustiva do Notepad++
        npp_paths = [
            find_executable('notepad++'),
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe"
        ]
        npp_bin = next((p for p in npp_paths if p and os.path.exists(p)), None)
        
        if npp_bin:
            print(f"   {Fore.CYAN}> [EDITOR] Invocando Notepad++ na linha {line}...{Style.RESET_ALL}")
            sub_popen([npp_bin, f"-n{line}", "-nosession", abs_path], shell=False)
            return
        sub_popen(['notepad.exe', abs_path], shell=False)
    else:
        for ed in ['micro', 'nano', 'vim']:
            if find_executable(ed):
                args = [abs_path + f':{line}'] if ed == 'micro' else [f'+{line}', abs_path]
                subprocess.run([ed] + args)
                return

def get_code_context(filepath: str, linenum: int) -> Optional[str]:
    """Recupera contexto de código local para o Dossiê."""
    if not filepath or not os.path.exists(filepath): return None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        start = max(0, linenum - 3)
        end = min(len(lines), linenum + 2)
        ctx = ""
        for i in range(start, end):
            is_target = (i == linenum - 1)
            marker = " >> " if is_target else "    "
            color = Fore.RED if is_target else Style.DIM
            ctx += f"    {color}{marker}{i+1:4} | {lines[i].strip()}{Style.RESET_ALL}\n"
        return ctx.rstrip()
    except: return None

def _render_platinum_dossier(d: dict, raw_tb: str):
    """Interface Suprema de Auditoria - Cores e Detalhes de Alta Definição."""
    w = 95
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

    print(f"\n{C} " + "═" * (w-2) + " ")
    print(f" {W}             DOSSIÊ CHIEF INSIGHT: RELATÓRIO DE INCIDENTE CRÍTICO               ")
    print(f"{C} " + "═" * (w-2) + " " + RST)

    # --- SEÇÃO 1: INFRAESTRUTURA ---
    print(f"  {W}ID EVENTO  : {Y}{d['id']:<10}{W}      POSTURA : {d['posture']}")
    print(f"  {W}HORÁRIO    : {Fore.BLUE}{d['timestamp']:<20}{W} ERRO    : {R}{d['technical_error']}{RST}")
    print(f"  {W}CLASSE     : {Y}{d['error_type']}{RST}")

    # --- SEÇÃO 2: HARDWARE (Sotéria) ---
    if d['soteria']:
        s = d['soteria']
        print(f"\n  {M}■ TRIANGULAÇÃO DA SOTÉRIA (Hardware Audit):{RST}")
        print(f"    {W}FALHA      : {R}{s.get('LEVEL', 'FATAL')}{RST} | {W}PID: {Y}{s.get('PID')}")
        print(f"    {W}MOTIVO     : {R}{s.get('MOTIVO')}{RST} ({s.get('DETAIL', 'Signal Intercepted')})")

    # --- SEÇÃO 3: EVIDÊNCIAS (Lazarus) ---
    print(f"\n  {G}■ TRIANGULAÇÃO DE EVIDÊNCIAS (Lazarus Protocol):{RST}")
    print(f"    {W}ALVO       : {Y}{os.path.basename(d['file'])}{RST}")
    print(f"    {W}LOCALIZAÇÃO: {C}{d['file']}:{d['line']}{RST}\n")
    
    # Chama a função de contexto definida no mesmo arquivo
    context = get_code_context(d['file'], d['line'])
    if context: print(context)

    # --- SEÇÃO 4: SEGURANÇA (Aegis) ---
    if "AEGIS" in raw_tb:
        print(f"\n  {R}🛡️  [AEGIS] Contexto de Intervenção:{RST}")
        aegis_msg = re.search(r"Exception: (.*)", raw_tb)
        if aegis_msg:
            print(f"    {W}DETALHE    : {Style.DIM}{aegis_msg.group(1)}{RST}")

    print(f"\n{C} " + "═" * (w-2) + " " + RST)
def analyze_crash(traceback_text: str) -> Dict[str, Any]:
    """Agregador Forense v43.2: Triangulação de Precisão e Extração de Erro."""
    
    # 1. Busca dados da Sotéria na Caixa Preta (Hardware)
    sot_tags = {}
    sot_file = Path(".doxoade/vulcan/last_crash.sot")
    if sot_file.exists():
        try:
            content = sot_file.read_text(encoding='utf-8')
            sot_tags = dict(re.findall(r"TAG_(.*?):\s*(.*)", content))
            sot_file.unlink() 
        except: pass

    # 2. Extração do Nome Técnico do Erro
    # Procura padrões como "OSError:", "ValueError:", etc no final do rastro
    tech_error = "HARDWARE_SIGNAL" if sot_tags else "SYSTEM_FAULT"
    tb_lines = [line.strip() for line in traceback_text.splitlines() if line.strip()]
    
    for line in reversed(tb_lines):
        if ":" in line and not line.startswith("File"):
            candidate = line.split(":")[0].strip()
            if "Error" in candidate or "Exception" in candidate or "Violation" in candidate:
                tech_error = candidate
                break

    # Se a Sotéria pegou um sinal específico de memória no Windows
    if sot_tags.get('DETAIL') and "0xc0000005" in sot_tags['DETAIL']:
        tech_error = "AccessViolation (Memory)"

    # 3. Triangulação de Localização (Cena do Crime)
    # PRIORIDADE 1: Rastro do Scribe (PRE-CALL) - Onde o código tentou entrar no abismo
    # PRIORIDADE 2: Local reportado pela Sotéria
    # PRIORIDADE 3: Traceback do Python
    loc_raw = sot_tags.get('RASTRO_LOC') or sot_tags.get('LOCAL')
    
    if loc_raw and ":" in loc_raw and "N/A" not in loc_raw:
        file_path, line = loc_raw.rsplit(':', 1)
    else:
        py_match = re.findall(r'File "(.*?)", line (\d+)', traceback_text)
        user_frames = [f for f in py_match if "site-packages" not in f[0] and "Lib" not in f[0]]
        file_path, line = user_frames[-1] if user_frames else py_match[-1] if py_match else ("N/A", 0)

    dossier = {
        'id': hashlib.md5(traceback_text.encode()).hexdigest()[:8].upper(),
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'file': file_path.replace("\\", "/"),
        'line': int(line),
        'technical_error': tech_error,
        'error_type': "VULCAN_NATIVE_SIGNAL" if sot_tags else "PYTHON_EXCEPTION",
        'posture': "🛡️ HARDENED (Aegis Active)" if "AEGIS" in traceback_text else "STANDARD",
        'soteria': sot_tags,
        'raw_tb': traceback_text
    }
    
    _render_platinum_dossier(dossier, traceback_text)
    return dossier

def activate_protocol(error_text: str):
    """Ponto de entrada principal."""
    if not error_text: return
    
    print('\n' + Fore.WHITE + Back.RED + '!' * 95 + Style.RESET_ALL)
    print(Fore.WHITE + Back.RED + '   [FATAL SYSTEM CRASH DETECTED]'.center(95) + Style.RESET_ALL)
    print(Fore.WHITE + Back.RED + '!' * 95 + Style.RESET_ALL)
    
    info = analyze_crash(error_text)
    
    print(f'\n{Fore.WHITE}{Style.BRIGHT}--- RESCUE OPTIONS ---{Style.RESET_ALL}')
    print(f'{Fore.YELLOW}1.{Style.RESET_ALL} [GIT] Revert file to {Fore.GREEN}STABLE{Style.RESET_ALL} version.')
    print(f'{Fore.YELLOW}2.{Style.RESET_ALL} [EDIT] Open {Fore.CYAN}Notepad++{Style.RESET_ALL} at error line.')
    print(f'{Fore.YELLOW}3.{Style.RESET_ALL} [INFO] View full raw traceback.')
    print(f'{Fore.YELLOW}0.{Style.RESET_ALL} [EXIT] Abort and do nothing.')
    
    choice = input(f'\n{Fore.CYAN}Choice (0-3): {Style.RESET_ALL}').strip()
    
    if choice == '1':
        print(f'{Fore.YELLOW}Reverting {info["file"]}...{Style.RESET_ALL}')
        run_git_command(['checkout', info['file']])
    elif choice == '2':
        _open_best_editor(info['file'], info['line'])
    elif choice == '3':
        print(f'\n{Fore.RED}--- RAW TRACEBACK ---{Style.RESET_ALL}')
        print(error_text)
    else:
        print(f'{Fore.DIM}Sessão encerrada sem modificações.{Style.RESET_ALL}')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as _f:
                activate_protocol(_f.read())
        except Exception as _e:
            logging.error(f'Lazarus fatal: {_e}')