# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_deploy.py
"""
🐉 TYPHON DEPLOY ENGINE v2.2 — Pipeline de Deploy Supervisionado com Separação Produção/Testes.
Modos suportados: PRODUCTION (com auto-backup), SANDBOX (isolado), TEST (chaos & forensics).
V2.2 — ÁRTEMIS DECOUPLED (ProDeNov 1.2.1 / Phanto-Crisis Cap. 1):
    Pré-geração síncrona de thumbnails desacoplada do hotpath do deploy.
    Geração convertida para lazy/on-demand (acionada em runtime pelos módulos 19a/19c).
    Deploy imediato (<200ms) e livre de warnings de metadata.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Literal

from doxoade.tools.doxcolors import Fore, Style
from .engine_lite_xl import LiteXLEngine
from .lite_xl_init_builder import LiteXLInitBuilder
from .typhon_doxly.doxly_khonsu_gate import DoxlyKhonsuGate

DeployMode = Literal["production", "sandbox", "test"]


def is_pid_alive(pid: int) -> bool:
    """Verifica se um PID específico ainda está em execução no SO."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def forensic_harvester(pid: int, deploy_dir: Path, poll_interval: float = 0.5) -> None:
    """
    🦅 Forensic Harvester em background para deploys de teste.
    Monitora session_log.txt e error.txt em tempo real sem travar a thread principal.
    """
    session_log = deploy_dir / "session_log.txt"
    error_txt = deploy_dir / "error.txt"
    last_session_size = session_log.stat().st_size if session_log.exists() else 0

    while is_pid_alive(pid):
        time.sleep(poll_interval)
        if session_log.exists():
            try:
                curr_size = session_log.stat().st_size
                if curr_size > last_session_size:
                    with open(session_log, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_session_size)
                        new_lines = f.read().splitlines()
                        for line in new_lines:
                            if any(w in line for w in ["ERROR", "CRITICAL", "GHOST", "CRASH"]):
                                print(f"\n{Fore.RED}🩺 [FORENSIC HARVEST] {line}{Fore.RESET}")
                    last_session_size = curr_size
            except Exception:
                pass

    # Pós-morte: necropsia rápida
    time.sleep(0.3)
    if error_txt.exists() and error_txt.stat().st_size > 0:
        print(f"\n{Fore.RED}{Style.BRIGHT}💥 [HARVESTER] O Lite XL encerrou com error.txt:{Style.RESET_ALL}")
        err_lines = error_txt.read_text(encoding="utf-8", errors="replace").splitlines()[:10]
        for el in err_lines:
            print(f"  {Fore.LIGHTRED_EX}↳ {el}{Fore.RESET}")

class TyphonDeployEngine:
    """Motor de Deploy com isolamento de modos: PRODUCTION, SANDBOX, TEST."""

    @classmethod
    def boot_watchdog(cls, mode: DeployMode, timeout: float = 8.0) -> bool:
        """🐺 Prova que o init bootou; senão autoriza fallback."""
        d = cls._get_deploy_dir(mode)
        session_log, error_txt = d / "session_log.txt", d / "error.txt"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if error_txt.exists() and error_txt.stat().st_size > 0:
                return False
            if session_log.exists() and "SOVEREIGN BOOT OK" in session_log.read_text(encoding="utf-8", errors="replace"):
                return True
            time.sleep(0.4)
        return False

    @classmethod
    def _get_deploy_dir(cls, mode: DeployMode) -> Path:
        """Retorna o diretório alvo baseado no modo operacional."""
        if mode == "production":
            return LiteXLEngine.get_user_dir()
        elif mode == "sandbox":
            return LiteXLEngine.get_sandbox_dir()
        elif mode == "test":
            test_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
            test_dir.mkdir(parents=True, exist_ok=True)
            return test_dir
        else:
            raise ValueError(f"Modo de deploy inválido: {mode}")

    @classmethod
    def _get_backup_dir(cls, mode: DeployMode) -> Path:
        """Retorna o diretório de backups por modo."""
        if mode == "production":
            bkp_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "backups" / "production"
        elif mode == "sandbox":
            bkp_dir = LiteXLEngine.get_sandbox_dir() / ".backups"
        else:
            bkp_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "backups" / "test"
        bkp_dir.mkdir(parents=True, exist_ok=True)
        return bkp_dir

    @classmethod
    def create_backup(cls, mode: DeployMode, reason: str = "pre-deploy") -> Tuple[bool, Optional[Path]]:
        """Cria backup timestampado do init.lua atual antes de qualquer mutação destrutiva."""
        try:
            deploy_dir = cls._get_deploy_dir(mode)
            init_path = deploy_dir / "init.lua"
            if not init_path.exists():
                return True, None
            backup_dir = cls._get_backup_dir(mode)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"init.lua.{timestamp}.{reason}.bak"
            backup_path = backup_dir / backup_name
            shutil.copy2(init_path, backup_path)
            cls._rotate_backups(backup_dir, max_backups=10)
            return True, backup_path
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao criar backup: {e}{Fore.RESET}")
            return False, None

    @classmethod
    def _rotate_backups(cls, backup_dir: Path, max_backups: int = 10) -> None:
        """Garante retenção de no máximo N snapshots históricos para evitar inchaço de disco."""
        try:
            backups = sorted(backup_dir.glob("init.lua.*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[max_backups:]:
                old_backup.unlink(missing_ok=True)
        except Exception:
            pass

    @classmethod
    def list_backups(cls, mode: DeployMode) -> list[Path]:
        """Lista todos os backups disponíveis ordenados pelo mais recente."""
        backup_dir = cls._get_backup_dir(mode)
        return sorted(backup_dir.glob("init.lua.*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def restore_backup(cls, mode: DeployMode, backup_path: Optional[Path] = None) -> Tuple[bool, str]:
        """Restaura um snapshot de backup específico ou o mais recente."""
        try:
            deploy_dir = cls._get_deploy_dir(mode)
            init_path = deploy_dir / "init.lua"
            if backup_path is None:
                backups = cls.list_backups(mode)
                if not backups:
                    return False, "Nenhum backup disponível para restauração."
                backup_path = backups[0]
            if not backup_path.exists():
                return False, f"Arquivo de backup inexistente: {backup_path}"
            if init_path.exists():
                cls.create_backup(mode, reason="pre-restore")
            shutil.copy2(backup_path, init_path)
            return True, f"Backup restaurado com sucesso: {backup_path.name}"
        except Exception as e:
            return False, f"Falha na restauração: {e}"

    @classmethod
    def exorcise_instances(cls, wait_seconds: float = 1.0) -> bool:
        """🕊️ Fechamento gracioso com salvamento de workspace + 🔪 Hard kill de processos zumbis."""
        try:
            from .lite_xl_process import LiteXLProcess
            if LiteXLProcess.is_process_alive():
                try:
                    LiteXLProcess.send_to_running_instance("__DOXOADE_GRACEFUL_QUIT__")
                except Exception:
                    pass
                deadline = time.time() + 1.5
                while time.time() < deadline:
                    if not LiteXLProcess.is_process_alive():
                        break
                    time.sleep(0.1)

            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Exorcismo parcial: {e}{Fore.RESET}")
            return False

    @classmethod
    def exorcise_mode_instance(cls, mode: DeployMode) -> None:
        """Encerra apenas o processo isolado do modo indicado via arquivo .pid."""
        deploy_dir = cls._get_deploy_dir(mode)
        pid_file = deploy_dir / f".{mode}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                else:
                    subprocess.run(["kill", "-9", str(pid)], capture_output=True)
                pid_file.unlink(missing_ok=True)
            except Exception:
                pass

    @classmethod
    def deploy(cls, mode: DeployMode = "production", force: bool = False, no_khonsu: bool = False) -> Dict[str, Any]:
        """
        Compila e instala o init.lua.
        Se no_khonsu=True, gera init.lua em texto plano (Plain Source), sem AOT e com Khonsu desativado.
        """
        deploy_dir = cls._get_deploy_dir(mode)
        deploy_dir.mkdir(parents=True, exist_ok=True)
        backup_path = None

        if mode == "test":
            for art in ["session_log.txt", "error.txt"]:
                target = deploy_dir / art
                if target.exists():
                    try: target.unlink()
                    except Exception: pass

        if mode == "production":
            ok, backup_path = cls.create_backup(mode, reason="pre-deploy")
            if not ok and not force:
                return {"success": False, "error": "Falha ao criar backup", "backup": None}

        try:
            py_anchor = deploy_dir / ".doxoade" / "python_path.txt"
            py_anchor.parent.mkdir(parents=True, exist_ok=True)
            py_anchor.write_text(sys.executable, encoding="utf-8")

            init_dest = deploy_dir / "init.lua"

            # 🛑 BYPASS DO KHONSU ATIVADO (Texto puro sem AOT)
            if no_khonsu:
                print(f"  {Fore.YELLOW}⚡ [PLAIN MODE] Khonsu AOT desativado. Gerando init.lua em texto puro...{Fore.RESET}")
                raw_source = LiteXLInitBuilder.generate_sovereign_init()
                # Injeta a desativação do Khonsu no topo do init.lua (strict-safe):
                # 'config' NÃO é global no Lite XL; strict.lua mata leitura de global
                # não declarada na linha 1. require local explícito = imunidade total.
                kill_switch = (
                    'local _dox_cfg = require "core.config"\n'
                    "_dox_cfg.doxoade_khonsu = false\n"
                )
                plain_source = kill_switch + raw_source
#                kill_switch = 'pcall(function() local c = require("core.config") c.doxoade_khonsu = false end)\n'
#                plain_source = kill_switch + raw_source
                init_dest.write_text(plain_source, encoding="utf-8")
                installed_size = len(plain_source)
                opt_mode = "plain_no_khonsu"
            else:
                gate_res = DoxlyKhonsuGate.compile_aot_supervisioned(target_mode=mode, verbose=True)
                if gate_res["success"] and gate_res.get("bytecode"):
                    init_dest.write_bytes(gate_res["bytecode"])
                    installed_size = len(gate_res["bytecode"])
                else:
                    init_dest.write_text(gate_res["source"], encoding="utf-8")
                    installed_size = len(gate_res["source"])
                opt_mode = gate_res.get("opt_mode", "plain")

            return {
                "success": True,
                "mode": mode,
                "init": init_dest,
                "backup": backup_path,
                "size": installed_size,
                "opt_mode": opt_mode,
                "error": None,
            }
        except Exception as e:
            if mode == "production" and backup_path and backup_path.exists():
                shutil.copy2(backup_path, deploy_dir / "init.lua")
            return {"success": False, "error": str(e), "backup": backup_path}

    @classmethod
    def launch(cls, mode: DeployMode, exorcise: bool = True) -> Optional[int]:
        """Lança a instância do Lite XL no ambiente e variáveis do modo escolhido."""
        deploy_dir = cls._get_deploy_dir(mode)
        exe = LiteXLEngine.find_executable()
        if not exe:
            print(f"{Fore.RED}✖ Executável do Lite XL não encontrado no sistema.{Fore.RESET}")
            return None

        if exorcise:
            if mode == "production":
                cls.exorcise_instances(wait_seconds=0.4)
            else:
                cls.exorcise_mode_instance(mode)

        env = os.environ.copy()
        env["LITE_USERDIR"] = str(deploy_dir)
        env["XDG_CONFIG_HOME"] = str(deploy_dir.parent)
        env["DOXOADE_DEPLOY_MODE"] = mode

        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        project_dir = os.getcwd()

        try:
            proc = subprocess.Popen(
                [str(exe), project_dir],
                env=env,
                creationflags=CREATE_NEW_CONSOLE,
                close_fds=(sys.platform != "win32"),
            )
            pid = proc.pid
            pid_file = deploy_dir / f".{mode}.pid"
            pid_file.write_text(str(pid), encoding="utf-8")
            print(f"{Fore.GREEN}✔ Instância Lite XL lançada [{mode.upper()}] (PID: {pid}){Fore.RESET}")
            return pid
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao lançar processo: {e}{Fore.RESET}")
            return None

    @classmethod
    def print_status(cls, target_mode: Optional[DeployMode] = None) -> None:
        """Exibe o diagnóstico e integridade de todos os modos de deploy."""
        modes: list[DeployMode] = [target_mode] if target_mode else ["production", "sandbox", "test"]
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🐉 STATUS DOS AMBIENTES DE DEPLOY TYPHON{Style.RESET_ALL}\n")

        for m in modes:
            ddir = cls._get_deploy_dir(m)
            init_file = ddir / "init.lua"
            pid_file = ddir / f".{m}.pid"

            is_running = False
            active_pid = None
            if pid_file.exists():
                try:
                    active_pid = int(pid_file.read_text().strip())
                    is_running = is_pid_alive(active_pid)
                except Exception:
                    pass

            status_icon = f"{Fore.GREEN}● ATIVO{Fore.RESET}" if is_running else f"{Fore.LIGHTBLACK_EX}○ PARADO{Fore.RESET}"
            init_size = f"{init_file.stat().st_size:,} bytes" if init_file.exists() else "AUSENTE"

            print(f"  {Style.BRIGHT}[{m.upper():<10}]{Style.RESET_ALL} {status_icon}")
            print(f"     ├─ Diretório : {Fore.LIGHTBLACK_EX}{ddir}{Fore.RESET}")
            print(f"     ├─ Init.lua  : {Fore.WHITE}{init_size}{Fore.RESET}")
            if active_pid and is_running:
                print(f"     └─ Processo  : {Fore.CYAN}PID {active_pid}{Fore.RESET}")
            else:
                backups_count = len(cls.list_backups(m))
                print(f"     └─ Backups   : {Fore.WHITE}{backups_count} snapshots salvos{Fore.RESET}")
            print()
            
    # ═══════════════════════════════════════════════════════════
    # 🖼️ ÁRTEMIS — PRÉ-GERAÇÃO DE THUMBNAILS (delegada pelo apêndice)
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def _pre_generate_thumbnails(cls, deploy_dir: Path) -> Tuple[bool, str]:
        """Pré-gera thumbnails binárias .thumb.rlebin para todas as imagens do projeto."""
        try:
            project_root = Path.cwd()
            images_dir = project_root / ".doxoade" / "assets" / "images"
            
            if not images_dir.exists():
                return True, "Sem imagens para processar"
            
            image_files = list(images_dir.glob("*.png"))
            if not image_files:
                return True, "Sem imagens PNG encontradas"
            
            print(f"🖼️  [ÁRTEMIS] Pré-gerando {len(image_files)} thumbnails binárias...")
            
            generated = 0
            errors = 0
            
            for img_path in image_files:
                try:
                    # ✅ CORREÇÃO: Garante tratamento como objeto Path, evitando .get() em strings
                    p = Path(img_path) if isinstance(img_path, str) else img_path
                    filename = p.name  # Usa .name em vez de .get('filename')
                    thumb_path = p.with_suffix('.thumb.rlebin')
                    
                    script_content = f"""
    import sys
    from pathlib import Path
    try:
        from PIL import Image
        import struct
        
        src = Path(r'{img_path}')
        dest = Path(r'{thumb_path}')
        
        img = Image.open(src).convert("RGB")
        ow, oh = img.size
        target_w = min(240, ow)
        target_h = int(oh * (target_w / ow))
        
        if (target_w, target_h) != (ow, oh):
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        pixels = img.load()
        rects = []
        
        for y in range(target_h):
            run_start = 0
            cur_c = pixels[0, y]
            for x in range(1, target_w):
                c = pixels[x, y]
                if c != cur_c:
                    rects.append((run_start, y, x - run_start, cur_c[0], cur_c[1], cur_c[2]))
                    run_start = x
                    cur_c = c
            rects.append((run_start, y, target_w - run_start, cur_c[0], cur_c[1], cur_c[2]))
        
        header = struct.pack("<7sBHHHHI", b"DOXRLE1", 1, target_w, target_h, ow, oh, len(rects))
        with open(dest, "wb") as f:
            f.write(header)
            for rx, ry, rw, r, g, b in rects:
                f.write(struct.pack("<HHHBBB", rx, ry, rw, r, g, b))
        print("[THUMB-OK]")
    except Exception as e:
        print(f"[THUMB-ERR] {{e}}")
    """
                    
                    script_path = deploy_dir / f"gen_thumb_{filename}.py"
                    script_path.write_text(script_content, encoding='utf-8')
                    
                    import subprocess
                    result = subprocess.run(
                        [sys.executable, str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if "[THUMB-OK]" in result.stdout:
                        generated += 1
                        script_path.unlink(missing_ok=True)
                    else:
                        errors += 1
                        
                except Exception as e:
                    errors += 1
            
            if errors == 0:
                return True, f"✅ {generated} thumbnails geradas"
            else:
                return True, f"⚠ {generated} geradas, {errors} erros"
                
        except Exception as e:
            return False, f"ÁRTEMIS falhou: {e}"

    # ═══════════════════════════════════════════════════════════
    # 🧪 LANÇAMENTO COM ISOLAMENTO
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def launch(cls, mode: DeployMode = "production", exorcise: bool = True) -> bool:
        """Lança o Lite XL no modo especificado preservando as outras instâncias."""
        if exorcise:
            if mode == "production":
                cls.exorcise_instances()
            else:
                cls.exorcise_mode_instance(mode)
            time.sleep(0.6)
        exe = LiteXLEngine.find_executable()
        if not exe:
            print(f"{Fore.RED}✖ Executável do Lite XL não encontrado.{Fore.RESET}")
            return False
        deploy_dir = cls._get_deploy_dir(mode)
        env = os.environ.copy()
        if mode != "production":
            env["LITE_USERDIR"] = str(deploy_dir)
            env["XDG_CONFIG_HOME"] = str(deploy_dir.parent)
        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(
                  [str(exe), "--userdir", str(deploy_dir)],
                  env=env,
                  creationflags=CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
            # (deploy_dir / f".{mode}.pid").write_text(str(proc.pid))
            # print(f"{Fore.GREEN}✔ Lite XL ({mode.upper()}) iniciado com sucesso (PID: {proc.pid}){Fore.RESET}")
            # return True
            pid_file = deploy_dir / f".{mode}.pid"
            pid_file.write_text(str(proc.pid), encoding="utf-8")
            
            print(f"{Fore.CYAN}🚀 Lite XL ({mode.upper()}) iniciado com sucesso (PID: {proc.pid}){Fore.RESET}")
            return proc.pid  # <--- ADICIONE ESTE RETORNO
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao lançar processo: {e}{Fore.RESET}")
            return False

    # ═══════════════════════════════════════════════════════════
    # 📊 STATUS E DIAGNÓSTICO
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def status(cls, mode: DeployMode) -> Dict[str, Any]:
        """Retorna status completo do modo."""
        deploy_dir = cls._get_deploy_dir(mode)
        init_path = deploy_dir / "init.lua"
        backups = cls.list_backups(mode)
        return {
            "mode": mode,
            "deploy_dir": str(deploy_dir),
            "init_exists": init_path.exists(),
            "init_size": init_path.stat().st_size if init_path.exists() else 0,
            "init_modified": datetime.fromtimestamp(init_path.stat().st_mtime).isoformat() if init_path.exists() else None,
            "backups_count": len(backups),
            "latest_backup": backups[0].name if backups else None,
        }

    @classmethod
    def print_status(cls, mode: Optional[DeployMode] = None) -> None:
        """Imprime status formatado de todos os modos ou de um específico."""
        modes = [mode] if mode else ["production", "sandbox", "test"]
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🐉 TYPHON DEPLOY STATUS{Style.RESET_ALL}\n")
        for m in modes:
            status = cls.status(m)
            mode_color = {
                "production": Fore.GREEN,
                "sandbox": Fore.BLUE,
                "test": Fore.YELLOW
            }.get(m, Fore.WHITE)
            print(f"{mode_color}{Style.BRIGHT}● {m.upper()}{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}Diretório:{Fore.RESET} {status['deploy_dir']}")
            if status['init_exists']:
                print(f"  {Fore.GREEN}✔ init.lua:{Fore.RESET} {status['init_size']:,} bytes")
                print(f"  {Fore.LIGHTBLACK_EX}  Modificado: {status['init_modified']}{Fore.RESET}")
            else:
                print(f"  {Fore.RED}✖ init.lua: AUSENTE{Fore.RESET}")
            if status['backups_count'] > 0:
                print(f"  {Fore.CYAN}💾 Backups:{Fore.RESET} {status['backups_count']} (último: {status['latest_backup']})")
            else:
                print(f"  {Fore.YELLOW}💾 Backups: Nenhum{Fore.RESET}")
            print()

# ═══════════════════════════════════════════════════════════════════════════════
# 🖼️ ÁRTEMIS HOOK V1.3 — wrapper module-level (APÓS a classe, indent 0)
# Plano A: delega a _pre_generate_thumbnails corrigido + deploy canônico.
# ═══════════════════════════════════════════════════════════════════════════════
# _ORIGINAL_DEPLOY = TyphonDeployEngine.deploy

# @classmethod
# def _deploy_with_thumbnails(mode: DeployMode = "production", force: bool = False, **kwargs) -> Dict[str, Any]:
#     # Repassa todos os argumentos (inclusive no_khonsu) para o deploy canônico
#     return _orig_deploy(mode=mode, force=force, **kwargs)

# # Aplica o monkey-patch
# TyphonDeployEngine.deploy = classmethod(_deploy_with_thumbnails)


def forensic_harvester(pid: int, deploy_dir: Path):
    """
    🕵️ HADES FORENSIC HARVESTER
    Monitora o processo do Lite XL em background.
    Se o processo morrer (crash) ou o Ghost Tracer detectar travamento,
    colhe e exibe a necropsia automaticamente no terminal.
    """
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
                import os
                os.kill(p, 0)
                return True
        except Exception:
            return False

    session_log = deploy_dir / "session_log.txt"
    error_txt = deploy_dir / "error.txt"
    ghost_trace = deploy_dir / ".doxoade" / "diagnostics" / "ghost_trace.txt"
    
    last_ghost_size = ghost_trace.stat().st_size if ghost_trace.exists() else 0
    
    print(f"{Fore.MAGENTA}🔮 [HARVESTER] Monitorando PID {pid}... (Pressione Ctrl+C no terminal para parar){Fore.RESET}")
    
    try:
        while True:
            time.sleep(1.0)
            
            # 1. Monitorar Ghost Tracer (Travamento de Frame > 50ms)
            if ghost_trace.exists():
                try:
                    current_size = ghost_trace.stat().st_size
                    if current_size > last_ghost_size:
                        with open(ghost_trace, "r", encoding="utf-8") as f:
                            f.seek(last_ghost_size)
                            new_lines = f.read().splitlines()
                        for line in new_lines:
                            print(f"\n{Fore.RED}👻 [GHOST DETECTED] {line}{Fore.RESET}")
                        last_ghost_size = current_size
                except Exception:
                    pass
                    
            # 2. Monitorar Morte do Processo (Crash Fatal)
            if not is_pid_alive(pid):
                time.sleep(0.5) # Aguarda o SO liberar os handles de arquivo
                print(f"\n{Fore.RED}{Style.BRIGHT}💥 [NECROPSIA AUTOMÁTICA] O Lite XL (PID {pid}) encerrou abruptamente!{Style.RESET_ALL}")
                
                if error_txt.exists() and error_txt.stat().st_size > 0:
                    print(f"\n{Fore.RED}🩺 CRASH REPORT (error.txt):{Fore.RESET}")
                    try:
                        print(error_txt.read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        pass
                        
                if session_log.exists():
                    try:
                        lines = session_log.read_text(encoding="utf-8", errors="replace").splitlines()
                        print(f"\n{Fore.YELLOW}📜 ÚLTIMOS 15 PASSOS DO BOOT (session_log.txt):{Fore.RESET}")
                        for line in lines[-15:]:
                            print(f"  {Fore.LIGHTBLACK_EX}↳ {line}{Fore.RESET}")
                    except Exception:
                        pass
                        
                print(f"\n{Fore.YELLOW}💡 O último módulo listado acima é o provável causador do crash.{Fore.RESET}")
                break
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 [HARVESTER] Monitoramento encerrado pelo usuário.{Fore.RESET}")

#TyphonDeployEngine.deploy = classmethod(_deploy_with_thumbnails)
