# hades_injection_test.py
"""
💀 HADES INJECTION TEST — Teste de Injeção Direta com Auto-Rollback.
Contorna o Single Instance (IPC) injetando o init do sandbox no userdir padrão.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def run_injection_test():
    user_dir = LiteXLEngine.get_user_dir()
    prod_init = user_dir / "init.lua"
    backup_init = user_dir / "init.lua.hades_backup"
    sandbox_init = LiteXLEngine.get_sandbox_dir() / "init.lua"
    exe = LiteXLEngine.find_executable()

    print("💀 HADES INJECTION TEST — Contornando Single Instance (IPC)")
    print(f"📂 Userdir: {user_dir}")
    print(f"📄 Init Produção: {prod_init}")
    print(f"📄 Init Sandbox: {sandbox_init}\n")

    # 1. VALIDAÇÃO
    if not sandbox_init.exists():
        print("✖ Init do sandbox não existe! Rode 'doxoade lite-xl typhon test-deploy' primeiro.")
        return
    
    if not prod_init.exists():
        print("✖ Init de produção não encontrado!")
        return

    # 2. BACKUP DE SEGURANÇA
    print("💾 Criando backup do init de produção...")
    shutil.copy2(prod_init, backup_init)
    print(f"✔ Backup salvo em: {backup_init}\n")

    # 3. INJEÇÃO
    print("💉 Injetando init do sandbox no userdir padrão...")
    shutil.copy2(sandbox_init, prod_init)
    print("✔ Injeção concluída.\n")

    # 4. EXORCISMO (Matar instâncias antigas para evitar IPC fantasma)
    print("🔪 Encerrando instâncias antigas do Lite XL...")
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    time.sleep(1.5)
    print("✔ Instâncias encerradas.\n")

    # 5. LANÇAMENTO
    print("⚡ Lançando Lite XL com o init de teste...")
    print("👀 A janela vai abrir. TESTE AS ABAS E O DOCK (Ctrl+Alt+E).")
    print("⏳ Quando terminar, FECHE A JANELA DO LITE XL para restaurar o backup.\n")
    
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen([str(exe), str(user_dir)], creationflags=CREATE_NEW_CONSOLE)
    
    # 6. AGUARDAR FECHAMENTO E RESTAURAR
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()
    
    print("\n🔄 Restaurando init de produção original...")
    if backup_init.exists():
        shutil.copy2(backup_init, prod_init)
        backup_init.unlink()
        print("✔ Rollback concluído com sucesso! Seu init original está de volta.")
    else:
        print("🚨 ERRO CRÍTICO: Backup não encontrado! Execute 'doxoade lite-xl rollback' manualmente.")

if __name__ == "__main__":
    run_injection_test()
