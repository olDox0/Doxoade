# blinding_canary_test.py
import os, time, shutil, subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

sandbox = LiteXLEngine.get_sandbox_dir()
exe = LiteXLEngine.find_executable()
sandbox_init = sandbox / "init.lua"

# 1. LIMPEZA
blind_canary = Path(r"C:\temp\doxoade_blind_canary.txt")
if blind_canary.exists(): blind_canary.unlink()
Path(r"C:\temp").mkdir(parents=True, exist_ok=True)

# 2. INJEÇÃO DO CANÁRIO CEGO (Caminho Absoluto)
canary_code = '''
-- 🐤 CANÁRIO CEGO (Prova de Fogo)
local _f = io.open("C:\\\\temp\\\\doxoade_blind_canary.txt", "w")
if _f then
    _f:write("O INIT DO SANDBOX FOI LIDO!\\n")
    _f:write("USERDIR=" .. tostring(USERDIR) .. "\\n")
    _f:write("TIME=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\\n")
    _f:close()
end
'''

if not sandbox_init.exists():
    print("✖ init.lua do sandbox não existe!")
else:
    content = sandbox_init.read_text(encoding="utf-8")
    # Remove canários antigos do topo se existirem
    if "-- 🐤 CANÁRIO" in content:
        content = content.split("-- 🐤 CANÁRIO", 1)[-1]
        # Remove a primeira linha que sobrou
        if content.startswith("\n"): content = content[1:]
    
    sandbox_init.write_text(canary_code + "\n" + content, encoding="utf-8")
    print("✔ Canário Cego injetado no topo absoluto.")

# 3. LANÇAMENTO
print(f"⚡ Lançando Lite XL (exe: {exe})...")
print(f"   Sandbox: {sandbox}")
CREATE_NEW_CONSOLE = 0x00000010 if os.name == 'nt' else 0
proc = subprocess.Popen(
    [str(exe), "--userdir", str(sandbox)],
    creationflags=CREATE_NEW_CONSOLE
)
print(f"✔ PID: {proc.pid}. Aguardando 6s...")
time.sleep(6)

# 4. VEREDITO
print("\n" + "="*60)
if blind_canary.exists():
    print("🎉 SUCESSO: O INIT DO SANDBOX FOI EXECUTADO!")
    print("-" * 40)
    print(blind_canary.read_text(encoding="utf-8"))
    print("-" * 40)
    print("💡 CONCLUSÃO: O Lite XL lê o init, mas o USERDIR interno está apontando para outro lugar.")
else:
    print("💀 FALHA CRÍTICA: O INIT DO SANDBOX NÃO FOI LIDO!")
    print("💡 CONCLUSÃO: O Lite XL está ignorando o --userdir ou o executável está errado.")
    print(f"   Verificando userdir padrão...")
    default_canary = Path.home() / ".config" / "lite-xl" / "BOOT_CANARY.txt"
    if default_canary.exists():
        print(f"   🚨 O canário foi criado no userdir PADRÃO: {default_canary}")
