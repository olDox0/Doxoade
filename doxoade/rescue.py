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

def _find_production_source(filename: str) -> Optional[Path]:
    """Caçador de Fontes: Localiza o arquivo original no projeto."""
    if not filename or filename == "N/A": return None
    p = Path(filename)
    if p.exists(): return p
    # Busca recursiva ignorando lixo
    candidates = [c for c in Path('.').rglob(p.name) if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build'])]
    return candidates[0] if candidates else None

def get_code_context(filepath: str, linenum: int) -> Optional[str]:
    """Extrai snippet de código com precisão Chief-Gold."""
    path = _find_production_source(filepath)
    if not path: return None
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        start, end = max(0, linenum - 3), min(len(lines), linenum + 2)
        ctx = ""
        for i in range(start, end):
            is_target = (i == linenum - 1)
            marker = " >> " if is_target else "    "
            color = Fore.RED if is_target else Style.DIM
            ctx += f"    {color}{marker}{i+1:4} | {lines[i].strip()}{Style.RESET_ALL}\n"
        return ctx.rstrip()
    except: return None

def _render_platinum_dossier(d: dict, raw_tb: str):
    """Interface de Auditoria de Platina - O Laudo Final."""
    w = 95
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

    print(f"\n " + "═" * (w-2) + " ")
    print(f" {W}             DOSSIÊ CHIEF INSIGHT: RELATÓRIO DE INCIDENTE CRÍTICO               ")
    print(f" " + "═" * (w-2) + " " + RST)

    print(f"  {W}ID EVENTO  : {Y}{d['id']:<10}{W}      POSTURA : {d['posture']}")
    print(f"  {W}INVOCAÇÃO  : {C}{d['invocation']}{RST}")
    print(f"  {W}HORÁRIO    : {Fore.BLUE}{d['timestamp']:<20}{W} ERRO    : {R}{d['technical_error']}{RST}")
    print(f"  {W}CLASSE     : {Y}{d['error_type']}{RST}")

    if d.get('insight'):
        print(f"\n  {Y}💡 [INSIGHT DE ENGENHARIA]:{RST}\n    {Style.DIM}{d['insight']}{RST}")

    if d['soteria']:
        s = d['soteria']
        print(f"\n  {M}■ TRIANGULAÇÃO DA SOTÉRIA (Hardware Audit):{RST}")
        print(f"    {W}FALHA      : {R}{s.get('LEVEL', 'FATAL')}{RST} | {W}PID: {Y}{s.get('PID', 'N/A')}")
        print(f"    {W}MOTIVO     : {R}{s.get('MOTIVO', 'SIGNAL')}{RST} ({s.get('DETAIL', 'No Detail')})")

    print(f"\n  {G}■ TRIANGULAÇÃO DE EVIDÊNCIAS (Lazarus Protocol):{RST}")
    actual_path = _find_production_source(d['file'])
    display_path = str(actual_path) if actual_path else d['file']
    print(f"    {W}ALVO       : {Y}{os.path.basename(display_path)}{RST}")
    print(f"    {W}LOCALIZAÇÃO: {C}{display_path}:{d['line']}{RST}\n")
    
    context = get_code_context(d['file'], d['line'])
    if context: print(context)
    print(f"\n " + "═" * (w-2) + " " + RST)

def analyze_crash(traceback_text: str, exit_code: int = None) -> Dict[str, Any]:
    """Agregador Forense Principal."""
    sot_tags = {}
    sot_match = re.search(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", traceback_text, re.DOTALL)
    if sot_match: sot_tags = dict(re.findall(r"TAG_(.*?):\s*(.*)", sot_match.group(1)))

    WIN_SIGNALS = {3221225477: "AccessViolation", 3221225621: "StackOverflow", 3221225481: "DivideByZero"}
    tech_error = "PYTHON_EXCEPTION"
    if exit_code in WIN_SIGNALS:
        tech_error = WIN_SIGNALS[exit_code]
        if not sot_tags: sot_tags['MOTIVO'] = f"SIGNAL_{hex(exit_code)}"

    py_match = re.findall(r'File "(.*?)", line (\d+)', traceback_text)
    user_frames = [f for f in py_match if not any(x in f[0] for x in ["site-packages", "Lib"])]
    file_path, line = user_frames[-1] if user_frames else py_match[-1] if py_match else ("N/A", 0)

    # Resolve rastro Sotéria para localização se disponível
    if sot_tags.get('RASTRO_LOC') and "N/A" not in sot_tags['RASTRO_LOC']:
        file_path, line = sot_tags['RASTRO_LOC'].rsplit(':', 1)

    dossier = {
        'id': hashlib.md5(traceback_text.encode()).hexdigest()[:8].upper(),
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'invocation': f"doxoade {' '.join(sys.argv[1:])}",
        'file': file_path, 'line': int(line),
        'technical_error': tech_error,
        'error_type': "VULCAN_NATIVE_SIGNAL" if (sot_tags or exit_code) else "PYTHON_EXCEPTION",
        'posture': "🛡️  HARDENED" if "AEGIS" in traceback_text else "STANDARD",
        'insight': None, 'soteria': sot_tags
    }
    _render_platinum_dossier(dossier, traceback_text)
    return dossier

def activate_protocol(error_text: str, exit_code: int = None):
    if not error_text: return
    print('\n' + Back.RED + '!' * 95 + Style.RESET_ALL)
    print(Back.RED + '[FATAL SYSTEM CRASH DETECTED]'.center(95) + Style.RESET_ALL)
    print(Back.RED + '!' * 95 + Style.RESET_ALL)
    info = analyze_crash(error_text, exit_code=exit_code)
    print(f'\n{Fore.WHITE}--- RESCUE OPTIONS ---\n{Fore.YELLOW}1. [GIT] Revert  2. [EDIT] Notepad++  3. [INFO] Traceback  0. [EXIT]{Style.RESET_ALL}')
    choice = input(f'\n{Fore.CYAN}Choice (0-3): {Style.RESET_ALL}').strip()
    if choice == '1': subprocess.run(['git', 'checkout', info['file']])
    elif choice == '2':
        npp = next((p for p in [r"C:\Program Files\Notepad++\notepad++.exe", "notepad++.exe"] if os.path.exists(p) or __import__('shutil').which(p)), 'notepad.exe')
        subprocess.Popen([npp, f"-n{info['line']}", os.path.abspath(info['file'])], shell=False)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as _f:
                activate_protocol(_f.read())
        except Exception as _e:
            logging.error(f'Lazarus fatal: {_e}')