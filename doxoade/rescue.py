# -*- coding: utf-8 -*-
# doxoade/doxoade/rescue.py
"""
Rescue System - Lazarus Protocol v61.0 Platinum Gold.
Agregador Forense: Sotéria + Aegis + Lazarus (Consolidado).
"""
import sys, os
from pathlib import Path
from typing import Dict, Any, Optional

from doxoade.tools.telemetry_tools.logger import chief_heartbeat
from doxoade.tools.doxcolors import Fore, Style, Back

# --- CONSTANTES TÁTICAS (Chief-Gold Standard) ---
C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                         Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                         Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

WIN_SIGNALS = {
    3221225477: ("AccessViolation (0xc0000005)", "Tentativa ilegal de violar a RAM física."),
    3221225481: ("DivideByZero", "Erro aritmético de hardware."),
    3221225621: ("StackOverflow", "A pilha de recursão explodiu."),
    3221226505: ("StackBufferOverrun (0xc0000409)", "A integridade da pilha foi destruída (Stack Smashing).")
}

# --- AUXILIARES ---

def _find_production_source(filename: str) -> Optional[Path]:
    """Caçador de Fontes: Localiza o arquivo original, ignorando caches."""
    if not filename or len(filename) < 3 or filename == "N/A": return None
    p = Path(filename)
    if p.exists(): return p
    candidates = [c for c in Path('.').rglob(p.name) if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build', 'shadow'])]
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
            color = R if is_target else Style.DIM
            ctx += f"    {color}{marker}{i+1:4} | {lines[i].strip()}{RST}\n"
        return ctx.rstrip()
    except: return None

# --- CORE ENGINE ---

def analyze_crash(traceback_text: str, exit_code: int = None) -> Dict[str, Any]:
    from .tools.vulcan.diagnostic.soteria.analyze_crash import CrashProcessor
    
    processor = CrashProcessor(project_root=".")
    dossier = processor.process(traceback_text, exit_code)
    _render_tactical_dossier(dossier) # Renderiza dossiê
    
    return dossier

def _render_tactical_dossier(d: dict):
    """Interface de Auditoria de Diamante - Renderização Pura."""
    w = 110
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

    DIM = Style.DIM
    
    # HEADER - Note que usamos ╠ no final para manter a caixa aberta para os dados
    print(f"\n{C}╔" + "═" * (w-2) + "╗")
    print(f"║{W}                    DOSSIÊ CHIEF INSIGHT: RELATÓRIO DE INTELIGÊNCIA TÁTICA                     {C}║")
    print(f"╠" + "═" * (w-2) + f"╣{RST}") # <--- CORRIGIDO: f-string para o RST funcionar

    # Use .get() para evitar crashes se o processador falhar
    print(f"  {W}🆔 ID EVENTO   : {Y}{d.get('id', 'N/A'):<20} {W}📅 HORÁRIO : {Fore.BLUE}{d.get('timestamp', 'N/A')}")
    print(f"  {W}🚀 INVOCAÇÃO   : {C}{d.get('invocation', 'doxoade')}{RST}")

    # --- SEÇÃO 2: DIAGNÓSTICO TÉCNICO ---
    print(f"\n  {R}■ CAUSA RAIZ (Necropsia de Sistema):{RST}")
    print(f"    {W}STATUS : {R}{d.get('technical_error', 'SYSTEM_FAULT')}{RST}")
    print(f"    {W}LAUDO  : {W}{d.get('explanation', 'Sem detalhes técnicos disponíveis.')}{RST}")
    
    # Análise Especial do Chief para NULL Pointers ou Corrupções
    sot = d.get('soteria', {})
    if sot.get('REG_RAX'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        # Exibe os 4 registradores principais
        print(f"    RAX: {Y}{sot.get('REG_RAX', 'N/A')}{RST} | RBX: {Y}{sot.get('REG_RBX', 'N/A')}{RST}")
        print(f"    RCX: {Y}{sot.get('REG_RCX', 'N/A')}{RST} | RDX: {Y}{sot.get('REG_RDX', 'N/A')}{RST}")

    # --- SEÇÃO 3: EVIDÊNCIAS DE HARDWARE ---
    if sot.get('RIP'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        # Formatação em grid para leitura rápida
        print(f"    RIP: {Y}{sot.get('RIP'):<18}{RST} | RSP: {Y}{sot.get('RSP', 'N/A')}{RST}")
        print(f"    RAX: {Y}{sot.get('RAX', '0x0'):<18}{RST} | RBX: {Y}{sot.get('RBX', '0x0')}{RST}")
        print(f"    RCX: {Y}{sot.get('RCX', '0x0'):<18}{RST} | RDX: {Y}{sot.get('RDX', '0x0')}{RST}")
    if sot.get('REG_RIP'):
        print(f"\n  {M}■ EVIDÊNCIAS DE HARDWARE (CPU Snapshot):{RST}")
        print(f"    {W}RAX (Acumulador) : {Y}{sot.get('REG_REG_RAX', 'N/A')}{RST}")
        print(f"    {W}RIP (Instrução) : {Y}{sot.get('REG_RIP', 'N/A')}{RST} | {W}RAX (Acumulador) : {Y}{sot.get('REG_RAX', 'N/A')}")
        print(f"    {W}RSP (Pilha)       : {Y}{sot.get('REG_RSP', 'N/A')}{RST}")

    # --- SEÇÃO 4: INVENTÁRIO DE ARENA (A Mesa do Crime) ---
    if d.get('inventory'):
        print(f"\n  {C}■ INVENTÁRIO DE OBJETOS (Uso da Memória Arena):{RST}")
        from collections import Counter
        counts = Counter([obj[0] for obj in d['inventory']])
        for tipo, qty in counts.items():
            # Barra visual de impacto proporcional (limitada a 20 chars)
            bar_size = min(qty, 20)
            bar = f"{C}{'█' * bar_size}{DIM}{'░' * (20 - bar_size)}"
            print(f"    {W}• {tipo:<20} {bar} {RST}{qty:>3} instâncias")

    if d.get('inventory_raw'):
        print(f"\n  {C}■ INVENTÁRIO DE ARENA (Objetos na RAM):{RST}")
        for item in d['inventory_raw']:
            # Formata: "memory_block | 1024 bytes"
            print(f"    {W}• {item}{RST}")

    # --- SEÇÃO 5: CENA DO CRIME (Lazarus Protocol) ---
    print(f"\n  {G}■ CENA DO CRIME (Triangulação de Código):{RST}")
    file_path = d.get('file', 'NATIVO')
    line_num = d.get('line', 0)
    print(f"    {W}ALVO FONTE  : {G}{os.path.basename(file_path)}{RST} | {W}COORDENADA: {C}{file_path}:{line_num}{RST}\n")
    
    context = get_code_context(file_path, line_num)
    if context: 
        print(context)
    else:
        print(f"    {DIM}(O código-fonte original não pôde ser resgatado para este frame){RST}")

    # --- SEÇÃO 6: CADEIA DE ENVOLVIMENTO ---
    if d.get('chain'):
        print(f"\n  {C}■ CADEIA DE ENVOLVIMENTO (Anatomia da Queda):{RST}")
        for idx, (func_name, loc) in enumerate(d['chain']):
            parts = loc.rsplit(':', 1)
            if len(parts) < 2: continue
            print(f"\n    {DIM}[{idx}]{RST} ↳ {G}{func_name:<25}{RST} ({os.path.basename(parts[0])}:{parts[1]})")
            
            # Mostra variável capturada para este frame
            var_info = d.get('soteria', {}).get(f'FRAME_VAR_{idx}')
            if var_info:
                print(f"        {Y}➔ ESTADO NO MOMENTO: {var_info}{RST}")

    # --- SEÇÃO 7: IO_DEBUG ---
    if d.get('io_history'):
        print(f"\n  {C}■ RASTRO DE OPERAÇÕES (Linha do Tempo IO_Debug):{RST}")
        for ev in d['io_history'][-10:]: # Últimas 10 ações
            print(f"    {W}➔ {ev}{RST}")

    # --- FOOTER ---
    print(f"\n{C}╚" + "═" * (w-2) + "╝" + RST)

def activate_protocol(error_text: str, exit_code: int = None):
    """Protocolo Lazarus: Menu de Intervenção Imediata após falha catastrófica."""
    if not error_text: return

    import subprocess

    chief_heartbeat("CHIEF", "RESCUE_ACTIVATED", {
        "reason": "Process Crash or Signal",
        "exit_code": exit_code
    })
    
    # 1. Alerta Visual de Impacto
    print('\n' + Back.RED + Style.BRIGHT + '!' * 110 + RST)
    print(Back.RED + Style.BRIGHT + '[FATAL SYSTEM CRASH DETECTED]'.center(110) + RST)
    print(Back.RED + Style.BRIGHT + '!' * 110 + RST)
    
    # 2. Executa a análise profunda e gera o Dossiê
    # O analyze_crash agora retorna o dicionário 'dossier' vindo do CrashProcessor
    info = analyze_crash(error_text, exit_code)
    
    # 3. Painel de Controle de Resgate (UX de Alta Resolução)
    print(f'\n  {W}--- 🛠  OPÇÕES DE INTERVENÇÃO (Chief-Gold) ---{RST}')
    
    file_label = os.path.basename(info["file"])
    if file_label == "NATIVO":
        print(f'  {Style.DIM}[1] [GIT]  (Indisponível para falha puramente nativa){RST}')
    else:
        print(f'  {Back.RED}1.{RST} {Fore.GREEN} [GIT]  Reverter alterações estáveis em {Y}{file_label}{RST}')
        
    print(f'  {Back.RED}2.{RST} {Fore.CYAN} [EDIT] Abrir Notepad++ na linha {Y}{info["line"]}{RST}')
    print(f'  {Back.RED}3.{RST} {Fore.RED} [INFO] Ver logs brutos (Traceback Completo){RST}')
    print(f'  {Back.RED}4.{RST} {Fore.YELLOW} [DEBUG] Ver Diagnóstico de Pipeline{RST}')
    print(f'  {Back.RED}0.{RST} {Fore.LIGHTMAGENTA_EX} [EXIT] Aceitar falha e encerrar sessão{RST}')
    
    try:
        # Prompt Estilizado
        choice = input(f'\n  {C}Sua decisão (0-3): {RST}').strip()
        
        if choice == '1' and file_label != "NATIVO":
            print(f'  {Y}[*] Executando Rollback via Git...{RST}')
            # Tenta reverter o arquivo para o último estado salvo (SAFE-MODE)
            res = subprocess.run(['git', 'checkout', '--', info['file']], capture_output=True)
            if res.returncode == 0:
                print(f'  {G}✔ Sucesso: {file_label} restaurado para a versão estável.{RST}')
            else:
                print(f'  {R}✘ Falha: Este arquivo não está sob controle do Git ou está em conflito.{RST}')
                
        elif choice == '2':
            # Localização Industrial do Notepad++ (Evita 'file not found' no Windows)
            import shutil
            npp_candidates = [
                r"C:\Program Files\Notepad++\notepad++.exe",
                r"C:\Program Files (x86)\Notepad++\notepad++.exe",
                "notepad++.exe"
            ]
            npp_bin = next((p for p in npp_candidates if os.path.exists(p) or shutil.which(p)), 'notepad.exe')
            
            print(f'  {C}[*] Invocando editor...{RST}')
            # Flag -n pula direto para a linha do erro no Notepad++
            target_abs = os.path.abspath(info['file'])
            subprocess.Popen([npp_bin, f"-n{info['line']}", "-nosession", target_abs], shell=False)
            print(f'  {G}✔ Editor aberto em {file_label} L{info["line"]}.{RST}')
            
        elif choice == '3':
            # Exibição do log sem as tags Sotéria para limpeza visual
            clean_log = error_text.replace("@SOTERIA_BEGIN@", "").replace("@SOTERIA_END@", "")
            print(f'\n{R}--- [ INÍCIO DO LOG BRUTO ] ---{RST}')
            print(f"{Style.DIM}{clean_log}{RST}")
            print(f'{R}--- [ FIM DO LOG ] ---{RST}')
#            input(f'\n{Style.DIM}Pressione Enter para prosseguir para a saída...{RST}')
        elif choice == '4':
            print(f"\n{C}🔬 [PIPELINE PROBE] Últimos Batimentos de Coração (Hades Engine):{RST}")
            try:
                from doxoade.database import get_db_connection
                conn = get_db_connection()
                rows = conn.execute('SELECT timestamp, subsystem, action, data FROM operational_logs ORDER BY id DESC LIMIT 10').fetchall()
                for r in reversed(rows):
                    ts = r['timestamp'][11:19]
                    print(f"  {Style.DIM}[{ts}]{RST} {Y}{r['subsystem']}{RST} | {C}{r['action']}{RST} ➔ {r['data']}")
                conn.close()
            except Exception as e:
                print(f"  {R}✘ Falha no DB: {e}{RST}")

    except KeyboardInterrupt:
        print(f'\n  {Y}[!] Intervenção abortada pelo usuário.{RST}')
    except Exception as e:
        print(f'\n  {R}[!] Erro no Protocolo Lazarus: {e}{RST}')
        
    # Encerra o processo de qualquer forma para evitar loops de erro
    sys.exit(1)