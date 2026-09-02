# crash_catcher.py
"""
🦅 HADES CRASH CATCHER — Captura o error.txt ANTES do rollback.
"""
import os, sys, time, shutil, subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

user_dir = LiteXLEngine.get_user_dir()
prod_init = user_dir / "init.lua"
backup_init = user_dir / "init.lua.crash_backup"
sandbox_init = LiteXLEngine.get_sandbox_dir() / "init.lua"
error_txt = user_dir / "error.txt"
session_log = user_dir / "session_log.txt"
exe = LiteXLEngine.find_executable()

print("🔪 Exorcizando instâncias antigas...")
if sys.platform == "win32":
    subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
else:
    subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
time.sleep(1.5)

print("💾 Backup do init de produção...")
shutil.copy2(prod_init, backup_init)

print("💉 Injetando init do sandbox...")
shutil.copy2(sandbox_init, prod_init)

# Limpa logs antigos para garantir que pegamos o novo
if error_txt.exists(): error_txt.unlink()
if session_log.exists(): session_log.unlink()

print("⚡ Lançando Lite XL... A JANELA VAI ABRIR.")
print("👀 INTERAJA, TESTE, E QUANDO O CRASH ACONTECER (OU VOCÊ FECHAR), O RELATÓRIO APARECERÁ AQUI.")
CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
proc = subprocess.Popen([str(exe)], creationflags=CREATE_NEW_CONSOLE)

try:
    proc.wait()
except KeyboardInterrupt:
    proc.kill()

print("\n" + "="*70)
print("🦅 RELATÓRIO FORENSE DO CRASH (HÓRUS)")
print("="*70)

if error_txt.exists():
    print("💥 ERROR.TXT CAPTURADO (A CAUSA RAIZ):")
    print("-" * 70)
    print(error_txt.read_text(encoding="utf-8", errors="replace"))
    print("-" * 70)
else:
    print("✅ Nenhum error.txt gerado (O Lite XL não crashou fatalmente no core).")

if session_log.exists():
    print("\n📜 SESSION_LOG.TXT (Últimas 20 linhas):")
    lines = session_log.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-20:]:
        print(f"  {line}")
else:
    print("\n⚠ session_log.txt não foi gerado (O 00_header_and_logger não rodou).")

print("\n🔄 Restaurando init de produção original...")
shutil.copy2(backup_init, prod_init)
backup_init.unlink()
print("✔ Rollback concluído. Seu init está salvo.")