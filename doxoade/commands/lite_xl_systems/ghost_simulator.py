# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/ghost_simulator.py
"""
👻 GHOST WINDOW SIMULATOR V3 — Isolamento Total da Produção.
Cria um ambiente efêmero próprio, NUNCA toca no USERDIR de produção.
NÃO usa TyphonDeployEngine.deploy() nem launch_with_safety_guard().
"""
import os
import sys
import time
import shutil
import threading
import subprocess
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.lite_xl_process import LiteXLProcess

# Payload Lua que causa travamentos de frame de 150ms a cada 2 segundos
GHOST_PAYLOAD = """
-- 👻 GHOST WINDOW SIMULATOR (Prova de Conceito do Ghost Tracer)
local core = require "core"
core.add_thread(function()
    coroutine.yield(3.0)
    core.log("👻 [GHOST SIMULATOR] Iniciando simulação de travamento de frame...")
    for i = 1, 5 do
        coroutine.yield(2.0)
        core.log("👻 [GHOST SIMULATOR] Congelando SDL2 por 150ms...")
        local t0 = os.clock()
        while (os.clock() - t0) < 0.150 do
            local _ = math.sqrt(os.clock())
        end
        core.log("👻 [GHOST SIMULATOR] Frame descongelado.")
    end
    core.log("👻 [GHOST SIMULATOR] Simulação concluída.")
end)
"""

# Ghost Tracer mínimo embutido
GHOST_TRACER_LUA = """
-- 👻 GHOST TRACER EMBUTIDO (Simulador V3)
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
if not core then return end
local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)
local tracer_log = diag_dir .. sep .. "ghost_trace.txt"
local GhostTracer = { last_frame = os.clock(), max_frame_ms = 50.0 }
if core.add_thread then
    core.add_thread(function()
        coroutine.yield(1.0)
        while true do
            coroutine.yield(0.1)
            local now = os.clock()
            local delta_ms = (now - GhostTracer.last_frame) * 1000
            if delta_ms > GhostTracer.max_frame_ms then
                local f = io.open(tracer_log, "a")
                if f then
                    f:write(string.format("[GHOST DETECTED] Frame travou por %.2fms | Hora: %s\\n",
                        delta_ms, os.date("%H:%M:%S")))
                    f:flush()
                    f:close()
                end
            end
            GhostTracer.last_frame = now
        end
    end)
end
"""


def forensic_harvester_v3(pid: int, sim_dir: Path):
    """Harvester isolado que monitora APENAS o diretório do simulador."""
    import ctypes

    def is_pid_alive(p):
        try:
            if hasattr(ctypes, 'windll'):
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x100000, False, p)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                os.kill(p, 0)
                return True
        except Exception:
            return False

    ghost_trace = sim_dir / ".doxoade" / "diagnostics" / "ghost_trace.txt"
    last_size = ghost_trace.stat().st_size if ghost_trace.exists() else 0

    print(f"{Fore.MAGENTA}🔮 [HARVESTER V3] Monitorando PID {pid} (isolado)...{Fore.RESET}")

    try:
        while True:
            time.sleep(1.0)
            if ghost_trace.exists():
                try:
                    cur_size = ghost_trace.stat().st_size
                    if cur_size > last_size:
                        with open(ghost_trace, "r", encoding="utf-8") as f:
                            f.seek(last_size)
                            for line in f.read().splitlines():
                                print(f"\n{Fore.RED}👻 {line}{Fore.RESET}")
                        last_size = cur_size
                except Exception:
                    pass
            if not is_pid_alive(pid):
                time.sleep(0.5)
                print(f"\n{Fore.RED}{Style.BRIGHT}💥 [HARVESTER] PID {pid} encerrou.{Style.RESET_ALL}")
                break
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Harvester encerrado.{Fore.RESET}")


def run_ghost_simulation():
    """Executa a simulação em ambiente 100% isolado da produção."""
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}👻 GHOST WINDOW SIMULATOR V3 — Isolamento Total{Style.RESET_ALL}\n")

    # 1. Criar diretório efêmero isolado
    sim_dir = Path.home() / ".doxoade_ghost_sim"
    if sim_dir.exists():
        shutil.rmtree(sim_dir, ignore_errors=True)
    sim_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / ".doxoade" / "diagnostics").mkdir(parents=True, exist_ok=True)

    print(f"{Fore.BLUE}🔧 Ambiente isolado criado: {sim_dir}{Fore.RESET}")

    # 2. Gerar init.lua mínimo com Ghost Tracer + Payload
    init_content = f"""
-- =============================================================================
-- GHOST SIMULATOR V3 — Init Isolado (NÃO usa templates de produção)
-- =============================================================================
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
if core and core.log then
    core.log("👻 [GHOST SIM V3] Boot isolado iniciado.")
end

-- Ghost Tracer embutido
{GHOST_TRACER_LUA}

-- Payload de congelamento
{GHOST_PAYLOAD}
"""
    init_path = sim_dir / "init.lua"
    init_path.write_text(init_content, encoding="utf-8")
    print(f"{Fore.YELLOW}💉 init.lua isolado gerado com Ghost Tracer + Payload.{Fore.RESET}")

    # 3. Encontrar executável do Lite XL
    exe = LiteXLProcess.find_executable()
    if not exe:
        print(f"{Fore.RED}✖ Executável do Lite XL não encontrado.{Fore.RESET}")
        shutil.rmtree(sim_dir, ignore_errors=True)
        return

    # 4. Matar APENAS instâncias anteriores do simulador
    pid_file = sim_dir / ".ghost_sim.pid"
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
            else:
                subprocess.run(["kill", "-9", str(old_pid)], capture_output=True)
        except Exception:
            pass

    # 5. Lançar Lite XL com LITE_USERDIR apontando para o diretório isolado
    env = os.environ.copy()
    env["LITE_USERDIR"] = str(sim_dir)
    env["XDG_CONFIG_HOME"] = str(sim_dir.parent)

    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [str(exe)],
        env=env,
        creationflags=CREATE_NEW_CONSOLE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid = proc.pid
    pid_file.write_text(str(pid), encoding="utf-8")

    print(f"\n{Fore.GREEN}✔ Lite XL (SIMULADOR) lançado com PID {pid}.{Fore.RESET}")
    print(f"{Fore.CYAN}⏳ Aguarde ~5s para o primeiro congelamento...{Fore.RESET}")
    print(f"{Fore.YELLOW}💡 Sua IDE de produção permanece INTACTA.{Fore.RESET}\n")

    # 6. Harvester isolado
    thread = threading.Thread(target=forensic_harvester_v3, args=(pid, sim_dir), daemon=True)
    thread.start()

    try:
        thread.join()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Encerrando simulador...{Fore.RESET}")
        try:
            proc.kill()
        except Exception:
            pass
    finally:
        # Limpeza do ambiente efêmero
        try:
            shutil.rmtree(sim_dir, ignore_errors=True)
        except Exception:
            pass
