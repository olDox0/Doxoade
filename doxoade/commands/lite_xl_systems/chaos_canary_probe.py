# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/chaos_canary_probe.py
"""
🐤 CANÁRIO FORENSE — Prova de Execução do Init do Sandbox.
Responde: O Lite XL está lendo o init.lua do sandbox?
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder


def run_canary_probe():
    """Injeta canário absoluto e verifica se o init foi lido."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🐤 CANÁRIO FORENSE — Prova de Execução{Style.RESET_ALL}\n")
    
    sandbox_dir = LiteXLEngine.get_sandbox_dir()
    sandbox_init = sandbox_dir / "init.lua"
    exe = LiteXLEngine.find_executable()
    
    if not exe:
        print(f"{Fore.RED}✖ Executável do Lite XL não encontrado.{Fore.RESET}")
        return
    
    # 1. Gera o init de caos
    print(f"{Fore.BLUE}🔧 Gerando init de caos...{Fore.RESET}")
    chaos_init = LiteXLInitBuilder.generate_chaos_init()
    
    # 2. Injeta o canário no topo absoluto
    canary_code = '''
-- 🐤 CANÁRIO ABSOLUTO (Prova de Execução)
local _canary_path = "C:\\\\temp\\\\doxoade_chaos_canary.txt"
local _f = io.open(_canary_path, "w")
if _f then
    _f:write("CANARY_ALIVE\\n")
    _f:write("USERDIR=" .. tostring(USERDIR or "NIL") .. "\\n")
    _f:write("PATHSEP=" .. tostring(PATHSEP or "NIL") .. "\\n")
    _f:write("TIME=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\\n")
    _f:write("INIT_SIZE=" .. tostring(#_G._DOXOADE_BOOT_REPORT.total if _G._DOXOADE_BOOT_REPORT else "UNKNOWN") .. "\\n")
    _f:close()
    print("[CANARY] Gravado em: " .. _canary_path)
else
    print("[CANARY] FALHA AO GRAVAR em: " .. _canary_path)
end
'''
    
    # Limpa canário antigo
    canary_file = Path("C:\\temp\\doxoade_chaos_canary.txt")
    if canary_file.exists():
        canary_file.unlink()
    
    # Injeta canário + init
    sandbox_init.write_text(canary_code + "\n" + chaos_init, encoding="utf-8")
    print(f"{Fore.GREEN}✔ Canário injetado no topo do init.lua{Fore.RESET}")
    
    # 3. Auditoria do init gerado
    print(f"\n{Fore.CYAN}📋 AUDITORIA DO INIT GERADO:{Fore.RESET}")
    print(f"   Tamanho: {len(chaos_init)} chars")
    print(f"   Contém '_doxoade_safe_boot': {chaos_init.count('_doxoade_safe_boot')}")
    print(f"   Contém '00_header_and_logger': {'00_header_and_logger' in chaos_init}")
    print(f"   Contém '00_01_api_probe': {'00_01_api_probe' in chaos_init}")
    
    # Verifica se há erros de sintaxe óbvios
    if chaos_init.count('end)') != chaos_init.count('_doxoade_safe_boot'):
        print(f"{Fore.YELLOW}⚠ Possível desbalanceamento de 'end)' no init{Fore.RESET}")
    
    # 4. Lança o Lite XL
    print(f"\n{Fore.BLUE}⚡ Lançando Lite XL no sandbox...{Fore.RESET}")
    print(f"   USERDIR: {sandbox_dir}")
    print(f"   PID: ", end="")
    
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [str(exe), "--userdir", str(sandbox_dir)],
        creationflags=CREATE_NEW_CONSOLE,
    )
    print(proc.pid)
    
    # 5. Aguarda e verifica
    print(f"\n{Fore.CYAN}⏳ Aguardando 6 segundos para boot...{Fore.RESET}")
    time.sleep(6)
    
    # 6. Veredito
    print(f"\n{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🦅 VEREDITO FORENSE{Style.RESET_ALL}")
    print(f"{'='*70}")
    
    if canary_file.exists():
        print(f"\n{Fore.GREEN}🐤 CANÁRIO: VIVO (O init.lua foi executado!){Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}{'-'*70}{Fore.RESET}")
        print(canary_file.read_text(encoding="utf-8"))
        print(f"{Fore.LIGHTBLACK_EX}{'-'*70}{Fore.RESET}")
        print(f"\n{Fore.GREEN}✔ CONCLUSÃO: O Lite XL lê o init do sandbox.{Fore.RESET}")
        print(f"{Fore.YELLOW}💡 O problema está nos hooks/logger que não estão gravando logs.{Fore.RESET}")
    else: 
        print(f"\n{Fore.RED}💀 CANÁRIO: MORTO (O init.lua NÃO foi executado){Fore.RESET}")
        print(f"{Fore.LIGHTBLACK_EX}{'-'*70}{Fore.RESET}")
        print(f"Procurado em: {canary_file}")
        print(f"{Fore.LIGHTBLACK_EX}{'-'*70}{Fore.RESET}")
        print(f"\n{Fore.RED}✖ CONCLUSÃO: O Lite XL está ignorando o --userdir{Fore.RESET}")
        print(f"{Fore.YELLOW}💡 Possíveis causas:{Fore.RESET}")
        print(f"   1. O --userdir não está sendo respeitado")
        print(f"   2. O init.lua tem erro de sintaxe fatal no topo")
        print(f"   3. O Lite XL está lendo o init do userdir padrão")
        
        # Verifica se o canário foi criado no userdir padrão
        default_canary = Path.home() / ".config" / "lite-xl" / "BOOT_CANARY.txt"
        if default_canary.exists():
            print(f"\n{Fore.RED}🚨 ALERTA: O canário foi criado no userdir PADRÃO!{Fore.RESET}")
            print(f"   Caminho: {default_canary}")
    
    # 7. Encerra o processo
    if proc.poll() is None:
        proc.kill()
        print(f"\n{Fore.BLUE}🔪 Processo Lite XL encerrado.{Fore.RESET}")


if __name__ == "__main__":
    run_canary_probe()
