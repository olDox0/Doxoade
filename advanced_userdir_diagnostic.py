# advanced_userdir_diagnostic.py
"""
🔍 ADVANCED USERDIR DIAGNOSTIC — Testa múltiplas hipóteses.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.tools.doxcolors import Fore, Style

def test_userdir_hypotheses():
    sandbox = LiteXLEngine.get_sandbox_dir()
    exe = LiteXLEngine.find_executable()
    sandbox_init = sandbox / "init.lua"
    
    print(f"{Fore.CYAN}{Style.BRIGHT}🔍 DIAGNÓSTICO AVANÇADO DO --userdir{Style.RESET_ALL}\n")
    print(f"Executável: {exe}")
    print(f"Sandbox: {sandbox}\n")
    
    # Hipótese 1: Erro de sintaxe no init.lua
    print(f"{Fore.CYAN}HIPÓTESE 1: Erro de sintaxe no init.lua{Fore.RESET}")
    
    # Cria init minimalista (sem módulos, só canário)
    minimal_init = '''
-- 🐤 INIT MINIMALISTA (Sem módulos, só canário)
print("[MINIMAL] Init do sandbox foi lido!")
print("[MINIMAL] USERDIR = " .. tostring(USERDIR))
local f = io.open(USERDIR .. "/MINIMAL_CANARY.txt", "w")
if f then
    f:write("MINIMAL_INIT_EXECUTED\\n")
    f:write("USERDIR=" .. tostring(USERDIR) .. "\\n")
    f:write("TIME=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\\n")
    f:close()
    print("[MINIMAL] Canário gravado com sucesso!")
else
    print("[MINIMAL] FALHA AO GRAVAR canário!")
end
'''
    
    # Backup do init atual
    if sandbox_init.exists():
        backup = sandbox / "init.lua.backup"
        shutil.copy2(sandbox_init, backup)
        print(f"   Backup criado: {backup.name}")
    
    # Injeta init minimalista
    sandbox_init.write_text(minimal_init, encoding="utf-8")
    print(f"   ✔ Init minimalista injetado\n")
    
    # Limpa canários antigos
    for canary_name in ["MINIMAL_CANARY.txt", "USERDIR_TEST.txt", "BOOT_CANARY.txt"]:
        canary = sandbox / canary_name
        if canary.exists():
            canary.unlink()
    
    # Lança com --userdir
    print(f"   Lançando Lite XL com --userdir...")
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    
    # Mata instâncias antigas
    subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    time.sleep(1.0)
    
    proc = subprocess.Popen(
        [str(exe), "--userdir", str(sandbox)],
        creationflags=CREATE_NEW_CONSOLE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    print(f"   PID: {proc.pid}. Aguardando 5 segundos...\n")
    time.sleep(5)
    
    # Verifica canário
    minimal_canary = sandbox / "MINIMAL_CANARY.txt"
    if minimal_canary.exists():
        print(f"{Fore.GREEN}✔ HIPÓTESE 1 CONFIRMADA: O --userdir FUNCIONA!{Fore.RESET}")
        print(f"   O problema está no init.lua soberano (erro de sintaxe).\n")
        print(f"   Conteúdo do canário:")
        print(f"   {'-'*60}")
        print(minimal_canary.read_text(encoding="utf-8"))
        print(f"   {'-'*60}\n")
    else:
        print(f"{Fore.RED}✖ HIPÓTESE 1 FALHOU: O --userdir NÃO está funcionando!{Fore.RESET}")
        print(f"   O Lite XL está ignorando a flag --userdir.\n")
        
        # Hipótese 2: Single Instance redirecionando
        print(f"{Fore.CYAN}HIPÓTESE 2: Single Instance redirecionando{Fore.RESET}")
        
        # Verifica se o canário foi criado no userdir padrão
        default_userdir = LiteXLEngine.get_user_dir()
        default_canary = default_userdir / "MINIMAL_CANARY.txt"
        
        if default_canary.exists():
            print(f"{Fore.YELLOW}⚠ CONFIRMADO: O canário foi criado no userdir PADRÃO!{Fore.RESET}")
            print(f"   Caminho: {default_canary}")
            print(f"   Isso confirma que o Lite XL está ignorando o --userdir.\n")
            print(f"   {Fore.CYAN}CAUSA PROVÁVEL:{Fore.RESET}")
            print(f"   - O Lite XL 2.1.8 pode ter mudado a sintaxe da flag")
            print(f"   - Ou há um bug no Single Instance que redireciona para o userdir padrão\n")
        else:
            print(f"   Canário não encontrado em nenhum lugar.\n")
    
    # Encerra o processo
    if proc.poll() is None:
        proc.kill()
    
    # Restaura o init original
    if sandbox_init.exists():
        backup = sandbox / "init.lua.backup"
        if backup.exists():
            shutil.copy2(backup, sandbox_init)
            backup.unlink()
            print(f"   ✔ Init original restaurado.\n")

if __name__ == "__main__":
    test_userdir_hypotheses()
