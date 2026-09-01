# sandbox_decisive_test.py
import os, time, shutil
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

sandbox = LiteXLEngine.get_sandbox_dir()
exe = LiteXLEngine.find_executable()
sovereign = LiteXLEngine.get_init_lua_path()          # init real COMPLETO
sandbox_init = sandbox / "init.lua"

# 1. REGENERA o init do sandbox a partir do soberano real
shutil.copy2(sovereign, sandbox_init)
content = sandbox_init.read_text(encoding="utf-8")

# 2. VERIFICA o conteúdo (isso responde à pista crítica)
print("=== DIAGNÓSTICO DO INIT ===")
print("É o SOVEREIGN completo?", "DOXOADE SOVEREIGN INIT" in content)
print("Qtd de módulos _doxoade_safe_boot:", content.count("_doxoade_safe_boot"))
print("Tem 00_header_and_logger?", "00_header_and_logger" in content)
print("Tem 00_01_api_probe?", "00_01_api_probe" in content)
print("Tamanho (chars):", len(content))

# Se NÃO for o soberano completo, aborta e avisa
if "DOXOADE SOVEREIGN INIT" not in content:
    print("\n✖ O init copiado NÃO é o soberano completo. Abortando.")
    raise SystemExit

# 3. LIMPA artefatos antigos
for rel in [".doxoade/api_guard/runtime_probe.json",
            ".doxoade/diagnostics/forensic_report.txt",
            "session_log.txt"]:
    p = sandbox / rel
    if p.exists():
        p.unlink()
print("\n✔ Artefatos antigos removidos.")

# 4. LANÇA via 'start' (idêntico ao lançamento manual)
cmd = f'start "" "{exe}" --userdir "{sandbox}"'
print("⚡ Lançando via 'start' (equivalente ao manual)...")
os.system(cmd)
print("Aguardando 8s...")
time.sleep(8)

# 5. VEREDITO
probe   = sandbox / ".doxoade" / "api_guard" / "runtime_probe.json"
forensic = sandbox / ".doxoade" / "diagnostics" / "forensic_report.txt"
session = sandbox / "session_log.txt"
print("\n=== VEREDITO ===")
print("Probe recriado?   ", probe.exists())
print("Forensic recriado?", forensic.exists())
print("Session recriado? ", session.exists())
