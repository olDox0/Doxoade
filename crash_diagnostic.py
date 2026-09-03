# crash_diagnostic.py
"""
🦅 CRASH DIAGNOSTIC — Captura error.txt e identifica o módulo culpado.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def run_diagnostic():
    user_dir = LiteXLEngine.get_user_dir()
    prod_init = user_dir / "init.lua"
    backup_init = user_dir / "init.lua.crash_diag_backup"
    sandbox_init = LiteXLEngine.get_sandbox_dir() / "init.lua"
    error_txt = user_dir / "error.txt"
    session_log = user_dir / "session_log.txt"
    exe = LiteXLEngine.find_executable()
    
    print("🦅 CRASH DIAGNOSTIC — Captura Forense Completa")
    print(f"📂 Userdir: {user_dir}")
    print(f"📄 Executável: {exe}\n")
    
    # 1. EXORCISMO
    print("🔪 Exorcizando instâncias antigas...")
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    time.sleep(1.5)
    print("✔ Instâncias encerradas.\n")
    
    # 2. BACKUP
    print("💾 Backup do init de produção...")
    shutil.copy2(prod_init, backup_init)
    print(f"✔ Backup salvo: {backup_init}\n")
    
    # 3. INJEÇÃO
    print("💉 Injetando init soberano completo...")
    shutil.copy2(sandbox_init, prod_init)
    print("✔ Injeção concluída.\n")
    
    # 4. LIMPEZA DE LOGS ANTIGOS
    if error_txt.exists():
        error_txt.unlink()
    if session_log.exists():
        session_log.unlink()
    print("✔ Logs antigos removidos.\n")
    
    # 5. LANÇAMENTO
    print("⚡ Lançando Lite XL...")
    print("👀 A janela vai abrir (ou crashar). Aguarde 8 segundos.\n")
    
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen([str(exe)], creationflags=CREATE_NEW_CONSOLE)
    
    time.sleep(8)
    
    # 6. CAPTURA FORENSE
    print("=" * 70)
    print("🦅 RELATÓRIO FORENSE COMPLETO")
    print("=" * 70)
    
    if error_txt.exists():
        print("\n💥 ERROR.TXT CAPTURADO (CAUSA RAIZ DO CRASH):")
        print("-" * 70)
        error_content = error_txt.read_text(encoding="utf-8", errors="replace")
        print(error_content)
        print("-" * 70)
        
        # Extrai o módulo culpado
        print("\n🔍 ANÁLISE DO MÓDULO CULPADO:")
        for line in error_content.splitlines():
            if "init.lua:" in line and ":" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        line_no = int(parts[1].strip())
                        print(f"   Linha do crash: {line_no}")
                        
                        # Lê o init para encontrar qual módulo está nessa linha
                        init_content = prod_init.read_text(encoding="utf-8")
                        init_lines = init_content.splitlines()
                        
                        # Procura o template mais próximo antes da linha do crash
                        current_template = "UNKNOWN"
                        for i in range(line_no - 1, -1, -1):
                            if i < len(init_lines):
                                if "[TEMPLATE:" in init_lines[i]:
                                    current_template = init_lines[i]
                                    break
                        
                        print(f"   Template suspeito: {current_template}")
                    except:
                        pass
    else:
        print("\n✅ Nenhum error.txt gerado (O Lite XL não crashou fatalmente)")
    
    if session_log.exists():
        print("\n📜 SESSION_LOG (últimas 30 linhas):")
        print("-" * 70)
        log_content = session_log.read_text(encoding="utf-8", errors="replace")
        lines = log_content.splitlines()
        for line in lines[-30:]:
            print(f"   {line}")
        print("-" * 70)
    else:
        print("\n⚠ session_log.txt não foi gerado")
    
    # 7. RESTAURA BACKUP
    print("\n🔄 Restaurando init de produção original...")
    shutil.copy2(backup_init, prod_init)
    backup_init.unlink()
    print("✔ Rollback concluído.\n")
    
    # 8. ENCERRA O PROCESSO
    if proc.poll() is None:
        proc.kill()
        print("🔪 Processo Lite XL encerrado.")

if __name__ == "__main__":
    run_diagnostic()