# sandbox_forensic_probe.py
"""
🦅 HÓRUS FORENSIC PROBE — Sistema de Verificação de Boot do Sandbox.
Responde: Onde (USERDIR real), O Que (Init foi lido?), Por Que (Crash?), Quem (Qual módulo?).
"""
import os
import time
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def run_forensic_probe():
    sandbox = LiteXLEngine.get_sandbox_dir()
    exe = LiteXLEngine.find_executable()
    sandbox_init = sandbox / "init.lua"
    
    print(f"🔍 SANDBOX FORENSIC PROBE (Hórus/Anúbis)")
    print(f"📂 Sandbox Dir: {sandbox}")
    print(f"📄 Sandbox Init: {sandbox_init}\n")

    # 1. LIMPEZA TOTAL DE ARTEFATOS
    for rel in [".doxoade/api_guard/runtime_probe.json",
                ".doxoade/diagnostics/forensic_report.txt",
                "session_log.txt", "error.txt", "BOOT_CANARY.txt"]:
        p = sandbox / rel
        if p.exists():
            p.unlink()
    print("✔ Artefatos antigos removidos.\n")

    # 2. INJEÇÃO DO CANÁRIO (Prova de Execução e USERDIR)
    canary_code = '''
-- 🐤 CANÁRIO FORENSE (Hórus)
local _userdir = USERDIR or "NIL_USERDIR"
local _pathsep = PATHSEP or "/"
local _canary_path = _userdir .. _pathsep .. "BOOT_CANARY.txt"
local _f = io.open(_canary_path, "w")
if _f then
    _f:write("CANARY_ALIVE\\n")
    _f:write("USERDIR=" .. _userdir .. "\\n")
    _f:write("TIME=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\\n")
    _f:close()
    print("[CANARY] Gravado em: " .. _canary_path)
else
    print("[CANARY] FALHA AO GRAVAR em: " .. _canary_path)
end
'''
    
    if not sandbox_init.exists():
        print("✖ init.lua do sandbox não existe! Rode 'doxoade lite-xl typhon test-deploy' primeiro.")
        return

    # Lê o conteúdo atual para auditoria
    original_content = sandbox_init.read_text(encoding="utf-8")
    
    # Injeta o canário no topo absoluto
    sandbox_init.write_text(canary_code + "\n" + original_content, encoding="utf-8")
    print("✔ Canário forense injetado no topo do init.lua.\n")

    # 3. LANÇAMENTO DO SANDBOX
    print("⚡ Lançando Lite XL no Sandbox...")
    CREATE_NEW_CONSOLE = 0x00000010 if os.name == 'nt' else 0
    proc = subprocess.Popen(
        [str(exe), "--userdir", str(sandbox)],
        creationflags=CREATE_NEW_CONSOLE
    )
    
    print(f"✔ PID Lançado: {proc.pid}. Aguardando 6 segundos para boot...\n")
    time.sleep(6)
    
    if proc.poll() is not None:
        print(f"⚠ O processo Lite XL morreu prematuramente! Exit Code: {proc.returncode}")
    else:
        print("✔ Processo Lite XL está vivo (não crashou no boot).")
        proc.kill() # Encerra para limpar

    # 4. EXTRAÇÃO DE EVIDÊNCIAS (O TRIBUNAL DE HÓRUS)
    print("\n" + "="*60)
    print("🦅 RELATÓRIO FORENSE (HÓRUS)")
    print("="*60)
    
    # 4.1. Canário (Onde e O Que)
    canary_file = sandbox / "BOOT_CANARY.txt"
    if canary_file.exists():
        print("\n🐤 CANÁRIO: VIVO (O init.lua foi executado!)")
        print("-" * 40)
        print(canary_file.read_text(encoding="utf-8"))
        print("-" * 40)
    else:
        print("\n🐤 CANÁRIO: MORTO (O init.lua NÃO foi executado)")
        print(f"   Procurado em: {canary_file}")
        print("   💡 Dica: O Lite XL pode estar ignorando o --userdir, ou o init.lua tem erro de sintaxe no topo.")

    # 4.2. Session Log (Quem)
    session_log = sandbox / "session_log.txt"
    if session_log.exists():
        print("\n📜 SESSION LOG: PRESENTE (O 00_header_and_logger.lua rodou)")
        log_content = session_log.read_text(encoding="utf-8", errors="replace")
        for line in log_content.splitlines():
            if "03b" in line or "16" in line or "ERROR" in line or "FAIL" in line or "CANARY" in line or "safe_boot" in line:
                print(f"   {line}")
    else:
        print("\n📜 SESSION LOG: AUSENTE (O 00_header_and_logger.lua não gravou)")

    # 4.3. Error Log (O Crash Fatal)
    error_txt = sandbox / "error.txt"
    if error_txt.exists():
        print("\n💥 ERROR.TXT (CRASH REPORT DO LITE XL): PRESENTE")
        print("-" * 40)
        print(error_txt.read_text(encoding="utf-8", errors="replace"))
        print("-" * 40)
    else:
        print("\n💥 ERROR.TXT: AUSENTE (Nenhum crash fatal do core)")

    # 4.4. Auditoria do Init (Ma'at)
    print("\n📄 AUDITORIA DO INIT.LUA (Ma'at)")
    print(f"   Tamanho: {len(original_content)} chars")
    print(f"   Contém '03b_tab_compact_staircase': {'03b_tab_compact_staircase' in original_content}")
    print(f"   Contém '16_open_editors_dock': {'16_open_editors_dock' in original_content}")
    safe_boots = original_content.count("_doxoade_safe_boot")
    print(f"   Blocos _doxoade_safe_boot: {safe_boots}")

if __name__ == "__main__":
    run_forensic_probe()
