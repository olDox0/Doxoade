# sandbox_isolation_test.py
import subprocess, time, os, sys
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

sandbox = LiteXLEngine.get_sandbox_dir()
exe = LiteXLEngine.find_executable()
print(f"Executável: {exe}")

probe   = sandbox / ".doxoade" / "api_guard" / "runtime_probe.json"
forensic = sandbox / ".doxoade" / "diagnostics" / "forensic_report.txt"
session = sandbox / "session_log.txt"

# 1. LIMPA ARTEFATOS ANTIGOS
for p in [probe, forensic, session]:
    if p.exists():
        p.unlink()
print("✔ Artefatos antigos removidos.")

# 2. LANÇAMENTO COM CONSOLE REAL (A mágica do Windows)
# CREATE_NEW_CONSOLE (0x10) força o Windows a criar uma janela de console para o processo filho.
CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0

proc = subprocess.Popen(
    [str(exe), "--userdir", str(sandbox)],
    env=os.environ,               # Herda as variáveis de ambiente (USERPROFILE, etc)
    creationflags=CREATE_NEW_CONSOLE,
    # SEM stdout=PIPE ou stderr=PIPE (deixa o Lite XL respirar)
)

print(f"⚡ Lite XL lançado (PID: {proc.pid}). Uma nova janela de console deve abrir. Aguardando 8s...")
time.sleep(8)

# 3. VERIFICAÇÃO DE VIDA
poll = proc.poll()
print(f"Poll após 8s: {poll} (None = vivo, número = exit code de crash)")

if poll is None:
    proc.kill()
    print("✖ Processo encerrado pelo timeout.")

# 4. VEREDITO
print("\n=== VEREDITO ===")
print("Probe recriado?   ", probe.exists())
print("Forensic recriado?", forensic.exists())
print("Session recriado? ", session.exists())
