# sandbox_minimal_test.py
import os, time, subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

sandbox = LiteXLEngine.get_sandbox_dir()
exe = LiteXLEngine.find_executable()
sandbox_init = sandbox / "init.lua"

# 1. LIMPA TUDO
for rel in [".doxoade/api_guard/runtime_probe.json",
            ".doxoade/diagnostics/forensic_report.txt",
            "session_log.txt", "error.txt", "BOOT_CANARY.txt"]:
    p = sandbox / rel
    if p.exists():
        p.unlink()

# 2. GERA INIT MINIMALISTA (só o canário, sem módulos)
minimal_init = '''
-- 🐤 INIT MINIMALISTA (Prova de --userdir)
print("[MINIMAL] Init do sandbox foi lido!")
print("[MINIMAL] USERDIR = " .. tostring(USERDIR))

local f = io.open(USERDIR .. "/BOOT_CANARY.txt", "w")
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

sandbox_init.write_text(minimal_init, encoding="utf-8")
print(f"✔ Init minimalista gerado: {sandbox_init}")
print(f"   Tamanho: {len(minimal_init)} chars")

# 3. LANÇA
print(f"\n⚡ Lançando Lite XL com --userdir...")
CREATE_NEW_CONSOLE = 0x00000010 if os.name == 'nt' else 0
proc = subprocess.Popen(
    [str(exe), "--userdir", str(sandbox)],
    creationflags=CREATE_NEW_CONSOLE
)
print(f"   PID: {proc.pid}. Aguardando 5s...")
time.sleep(5)
 
# 4. VEREDITO
canary = sandbox / "BOOT_CANARY.txt"
print("\n" + "="*60)
if canary.exists():
    print("🎉 SUCESSO: O --userdir FUNCIONA!")
    print("-" * 40)
    print(canary.read_text(encoding="utf-8"))
    print("-" * 40)
    print("💡 CONCLUSÃO: O problema está no init.lua soberano (erro de sintaxe).")
else:
    print("💀 FALHA: O --userdir NÃO está funcionando!")
    print("   O Lite XL está ignorando a flag --userdir.")
print("="*60)

if proc.poll() is None:
    proc.kill()
