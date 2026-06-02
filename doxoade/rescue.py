# -*- coding: utf-8 -*-
# doxoade/doxoade/rescue.py
"""
Rescue System - Lazarus Protocol v61.0 Platinum Gold.
Agregador Forense: Sotéria + Aegis + Lazarus (Consolidado).
"""
import sys
import os
import re
import json
import subprocess
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

def _view_align(text, width):
    """Alinha o texto compensando os caracteres invisíveis de cor ANSI."""
    import re
    # Regex que remove os códigos ANSI para contar o tamanho real visível
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean_text = ansi_escape.sub('', text)
    padding = width - len(clean_text)
    return text + (" " * max(0, padding))


def _find_production_source(filename: str) -> Optional[Path]:
    if not filename or len(filename) < 3 or filename in ["N/A", "NATIVO"]: return None
    p = Path(filename)
    if p.exists(): return p
    try:
        candidates = [c for c in Path('.').rglob(p.name) if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build', 'shadow'])]
        return candidates[0] if candidates else None
    except: return None

def get_code_context(filepath: str, linenum: int, context_lines: int = 2) -> Optional[str]:
    path = _find_production_source(filepath)
    if not path or linenum <= 0: return None
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        start = max(0, linenum - context_lines - 1)
        end = min(len(lines), linenum + context_lines)
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
    return processor.process(traceback_text, exit_code)

def _render_tactical_dossier(d: dict):
    """Interface de Auditoria de Diamante - Renderização Pura."""
    w = 110
    C, M, Y, R, W, G, RST = (Fore.CYAN+Style.BRIGHT, Fore.MAGENTA+Style.BRIGHT, 
                             Fore.YELLOW+Style.BRIGHT, Fore.RED+Style.BRIGHT, 
                             Fore.WHITE+Style.BRIGHT, Fore.GREEN+Style.BRIGHT, Style.RESET_ALL)

    DIM = Style.DIM
    
    # --- [CÁLCULO DE FORMATAÇÃO DO EXIT CODE] ---
    exit_raw = d.get('exit_code')
    is_nt_error = exit_raw is not None and (exit_raw > 255 or exit_raw < -1)
    if is_nt_error:
        # Se for erro de hardware, brilha em Vermelho
        exit_display = f"{Fore.RED}0x{exit_raw & 0xFFFFFFFF:08X}{RST}"
    else:
        exit_display = f"{Fore.YELLOW}{exit_raw}{RST}"

    print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
    print(Fore.CYAN + Style.BRIGHT + '[RELATÓRIO SOB ERRO]'.center(110) + RST + '\n')
    
    # Linha 1 do Header
    print(f"  {W}🆔 ID EVENTO   : {RST}{Fore.YELLOW}{d.get('id', 'N/A'):<20} {W}📅 HORÁRIO : {RST}{Fore.YELLOW}{d.get('timestamp', 'N/A')}")
    # Linha 2 do Header (Invocação + Exit Code)
    print(f"  {W}🚀 INVOCAÇÃO   : {RST}{Fore.YELLOW}{d.get('invocation', 'doxoade'):<20} {W}🚪 EXIT CODE : {RST}{Fore.YELLOW}{exit_display}{RST}")

    # --- SEÇÃO 2: DIAGNÓSTICO TÉCNICO ---
    print(f"\n  {C}■ CAUSA RAIZ (Necropsia de Sistema):{RST}")
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
    print(f"\n  {C}■ CENA DO CRIME (Triangulação de Código):{RST}")
    file_path = d.get('file', 'NATIVO')
    line_num = d.get('line', 0)
    print(f"    {W}ALVO FONTE  : {RST}{Fore.YELLOW}{os.path.basename(file_path)}{RST} | {W}COORDENADA: {RST}{Fore.YELLOW}{file_path}:{line_num}{RST}")
    
    context = get_code_context(file_path, line_num)
    if context: 
        print(context)
    else:
        print(f"    {DIM}(O código-fonte original não pôde ser resgatado para este frame){RST}")

    # --- SEÇÃO 6: CADEIA DE ENVOLVIMENTO ---
    if d.get('chain'):
        print(f"\n  {C}■ CADEIA DE ENVOLVIMENTO (Anatomia da Queda):{RST}")
        for idx, (func_name, loc) in enumerate(d['chain']):
            f_p, l_n = loc.rsplit(':', 1)
            is_py = ".py" in f_p.lower()
            label = "[PY]" if is_py else "[C]"
            color_f = Fore.YELLOW if is_py else G
            
            print(f"    {DIM}[{idx}]{RST} {M}{label}{RST} ↳ {color_f}{func_name:<25}{RST} ({os.path.basename(f_p)}:{l_n})")
            
            # [UPGRADE] Solicita 2 linhas de contexto para gerar o snippet de 5 linhas
            snip = get_code_context(f_p, int(l_n), context_lines=2)
            if snip:
                print(f"{snip}")

    # --- SEÇÃO 7: IO_DEBUG ---
    if d.get('io_history'):
        print(f"\n  {C}■ RASTRO DE OPERAÇÕES (Enriquecido com IO_Content):{RST}")
        for ev in d['io_history'][-10:]:
            # Exemplo de saída: ➔ Operation: printf | Data: "Corrompendo a Zona..."
            print(f"    {W}➔ {ev}{RST}")

def activate_protocol(error_text: str, exit_code: int = None):
    """Protocolo Lazarus: Menu de Intervenção Imediata."""
    from .tools.telemetry_tools.logger import chief_heartbeat
    import sys as _sys
    import os as _os
    import re

    if not error_text: 
        return

    # --- 1. RESOLUÇÃO DE CÓDIGO TÉCNICO ---
    # Se o exit_code não foi passado pelo SO, tentamos extrair do log bruto da Sotéria
    if exit_code is None:
        match = re.search(r"TAG_MOTIVO:\s*(0x[0-9a-fA-F]+|\d+)", error_text)
        if match:
            val = match.group(1)
            exit_code = int(val, 16) if val.startswith('0x') else int(val)
        else:
            exit_code = 1 # Fallback para erro genérico Python

    # --- 2. NECROPSIA (Análise Única) ---
    from .tools.vulcan.diagnostic.soteria.analyze_crash import CrashProcessor
    processor = CrashProcessor(project_root=".")
    # Processamos o erro uma única vez para obter todos os metadados
    info = processor.process(error_text, exit_code)
    
    # Filtro de Aborto: Se for um encerramento normal, não fazemos nada
    if info.get('technical_error') == "NORMAL_EXIT": 
        return

    # --- 3. TELEMETRIA ENRIQUECIDA (Hades Engine) ---
    # Agora o log registra o VEREDITO real (ex: Memory Corruption) em vez de apenas "Process Crash"
    chief_heartbeat("CHIEF", "RESCUE_ACTIVATED", {
        "verdict": info.get('technical_error', 'Process Crash'),
        "target": _os.path.basename(info.get('file', 'NATIVO')),
        "exit_code": exit_code
    })

    # --- 4. INTERFACE VISUAL ---
    print('\n' + Back.RED + '[SYSTEM CRASH DETECTED]'.center(110) + Style.RESET_ALL)
    
    # Renderiza o dossiê tático (Aquele com as coordenadas do crime)
    _render_tactical_dossier(info)
    
    # 3. Loop de Intervenção
    try:
        while True:
            print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
            print(Fore.CYAN + Style.BRIGHT + '[OPÇÕES DE INTERVENÇÃO]'.center(110) + RST + '\n\n')
            file_label   = _os.path.basename(info["file"])
            
            opt1 = f"{Back.RED}1.{RST} {Fore.GREEN} [GIT]  Reverter {Y}{file_label}{RST}"
            if file_label == "NATIVO":
                opt1 = f"{Style.DIM}[1] [GIT]  (Indisponível p/ falha nativa){RST}"

            opt2 = f"{Back.RED}2.{RST} {Fore.CYAN} [EDIT] Abrir Notepad++ Linha {Y}{info['line']}{RST}"
            opt3 = f"{Back.RED}3.{RST} {Fore.RED} [INFO] Ver logs brutos{RST}"
            opt4 = f"{Back.RED}4.{RST} {RST}{Fore.YELLOW} [DEBUG] Diagnóstico Pipeline{RST}"
            opt0 = f"{Back.RED}0.{RST} {Fore.LIGHTMAGENTA_EX} [EXIT] Encerrar sessão{RST}"

            # Renderização em Grade 2x2 usando o alinhador inteligente
            # Largura de 55 para caber bem em telas padrão de 110/120 colunas
            print(f"  {_view_align(opt1, 55)} {opt2}")
            print(f"  {_view_align(opt3, 55)} {opt4}")
            print(f"  {_view_align(opt0, 55)}")

            choices = input(f"\n  Sua decisão (ex: 34): ").strip()
            if '0' in choices: break

            try:
                for choice in choices:
                    if choice == '1' and file_label != "NATIVO":
                        subprocess.run(['git', 'checkout', '--', info['file']], capture_output=True)
                        print(f'  {Fore.GREEN}✔ Sucesso: {file_label} restaurado.{Style.RESET_ALL}')
                    if choice == '2':
                        # Localização Industrial do Notepad++ (Evita 'file not found' no Windows)
                        import shutil
                        npp_candidates = [
                            r"C:\Program Files\Notepad++\notepad++.exe",
                            r"C:\Program Files (x86)\Notepad++\notepad++.exe",
                            "notepad++.exe"
                        ]
                        npp_bin = next((p for p in npp_candidates if _os.path.exists(p) or shutil.which(p)), 'notepad.exe')
                        
                        print(f'  {C}[*] Invocando editor...{RST}')
                        # Flag -n pula direto para a linha do erro no Notepad++
                        target_abs = _os.path.abspath(info['file'])
                        subprocess.Popen([npp_bin, f"-n{info['line']}", "-nosession", target_abs], shell=False)
                        print(f'  {G}✔ Editor aberto em {file_label} L{info["line"]}.{RST}')
                        
                    if choice == '3':
                        print('\n' + Fore.RED+Style.BRIGHT + '_' * 110 + RST)
                        print(f"\n  {Fore.RED+Style.BRIGHT}■ [BRUTE LOG] Soteria Engine:{RST}\n")
                        # Exibição do log sem as tags Sotéria para limpeza visual
                        clean_log = error_text.replace("@SOTERIA_BEGIN@", "").replace("@SOTERIA_END@", "")
                        print(f'\n{R}--- [ INÍCIO DO LOG BRUTO ] ---{RST}')
                        print(f"{Style.DIM}{clean_log}{RST}")
                        print(f'{R}--- [ FIM DO LOG ] ---{RST}')
            #            input(f'\n{Style.DIM}Pressione Enter para prosseguir para a saída...{RST}')
                    if choice == '4':
                        print('\n' + Fore.RED+Style.BRIGHT + '_' * 110 + RST)
                        print(f"\n  {Fore.RED+Style.BRIGHT}■ [PIPELINE PROBE] Hades Engine:{RST}\n")
                        try:
                            from doxoade.database import get_db_connection
                            import json
                            conn = get_db_connection()
                            rows = conn.execute('SELECT timestamp, subsystem, action, data FROM operational_logs ORDER BY id DESC LIMIT 12').fetchall()
                            for r in reversed(rows):
                                # FIX: Corrigido de 's11' para '[11:19]'
                                ts = r['timestamp'][11:19] 
                                sys_label = f"{r['subsystem']:<10}"
                                act_label = f"{r['action']:<22}"
                                try:
                                    d_obj = json.loads(r['data'])
                                    # Limpa a visualização do JSON para o terminal
                                    d_str = ", ".join([f'"{k}": {v}' for k, v in d_obj.items()])
                                except:
                                    d_str = r['data']
                                
                                print(f"  {Style.DIM}[{ts}]{RST} {Fore.YELLOW}{sys_label}{RST} │ {C}{act_label}{RST} >> {W}{d_str}{RST}")
                            conn.close()
                        except Exception as e:
                            print(f"  {R}✘ Falha ao consultar Hades: {e}{RST}")
                break
            except Exception as e:
                from doxoade.tools.error_info import handle_error
                handle_error(e, context="activate_protocol", debug=True)
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="activate_protocol", debug=True)

    # --- FOOTER ---
    print('\n' + Fore.CYAN + Style.BRIGHT + '_' * 110 + RST)
    
    # --- O SELO FINAL ---
    # os._exit garante que o Lazarus não tente se auto-diagnosticar ao fechar
    import os
#    _os._exit(1) # obs: vejo que é melhor sys._exit.
    _sys.exit(exit_code if exit_code is not None else 1)