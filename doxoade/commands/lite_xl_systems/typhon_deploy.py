# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_deploy.py
"""
🐉 TYPHON DEPLOY ENGINE v2.2 — Pipeline de Deploy Supervisionado com Separação Produção/Testes.
Modos suportados: PRODUCTION (com auto-backup), SANDBOX (isolado), TEST (chaos & forensics).
V2.2 — ÁRTEMIS DECOUPLED (ProDeNov 1.2.1 / Phanto-Crisis Cap. 1):
    Pré-geração síncrona de thumbnails desacoplada do hotpath do deploy.
    Geração convertida para lazy/on-demand (acionada em runtime pelos módulos 19a/19c).
    Deploy imediato (<2
    00m
    s) e livre de warnings de metadata.
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
from typing import Dict, Any, Optional, Tuple, Literal, List

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
    def reset_mode(
        cls,
        mode: DeployMode,
        hard: bool = False,
        keep_backups: bool = True,
    ) -> Dict[str, Any]:
        """
        🧹 Reseta o ambiente de deploy para estado limpo.
        - hard=True: apaga também init.lua (força redeploy do zero).
        - keep_backups: preserva .doxoade/backups/ (rollback safety).
        Não toca em python_path.txt (âncora do venv).
        """
        import tempfile
        deploy_dir = cls._get_deploy_dir(mode)
        report: Dict[str, Any] = {
            "mode": mode,
            "dir": str(deploy_dir),
            "removed": [],
            "kept": [],
            "errors": [],
        }

        # 1. Matar instância viva desse modo (por PID file)
        try:
            cls.exorcise_mode_instance(mode)
        except Exception as e:
            report["errors"].append(f"exorcise: {e}")

        if not deploy_dir.exists():
            report["kept"].append("dir_not_found")
            return report

        # 2. Stash de backups se solicitado
        backups_dir = deploy_dir / ".doxoade" / "backups"
        backups_stash = None
        if keep_backups and backups_dir.exists():
            try:
                backups_stash = Path(tempfile.mkdtemp(prefix=f"dox_bkp_{mode}_"))
                shutil.copytree(backups_dir, backups_stash / "backups")
                report["kept"].append("backups")
            except Exception as e:
                report["errors"].append(f"backup_stash: {e}")
                backups_stash = None

        # 3. Lista de alvos (preserva python_path.txt e init.lua se !hard)
        items_to_nuke = [
            "session.lua", "session.json", "sovereign_session.lua",
            "user_settings.lua", "user_settings.lua.DISABLED",
            "session_log.txt", "error.txt", "font_cache.lua",
            "plugins_DISABLED", "workspace",
            f".{mode}.pid", ".deploy.lock", ".ipc_queue", ".ipc_processing",
            ".doxoade/diagnostics", ".doxoade/api_guard",
            ".doxoade/canvas_cache", ".doxoade/terminal_temp",
            ".doxoade/canonical_live", ".doxoade/shadow_harness",
            ".doxoade/staging", ".doxoade/sandbox",
        ]
        if hard:
            items_to_nuke.extend([
                "init.lua", "init.lua.stable", "init.lua.broken", "init.lua.plain",
            ])
        else:
            report["kept"].append("init.lua (soft reset)")
        if not keep_backups:
            items_to_nuke.append(".doxoade/backups")

        # Globs de PTY IPCs
        try:
            for pty_dir in deploy_dir.glob(".doxoade/terminal_pty_ipc*"):
                try:
                    items_to_nuke.append(str(pty_dir.relative_to(deploy_dir)))
                except Exception:
                    pass
        except Exception:
            pass

        for rel in items_to_nuke:
            target = deploy_dir / rel
            if not target.exists():
                continue
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                report["removed"].append(rel)
            except Exception as e:
                report["errors"].append(f"{rel}: {e}")

        # 4. Restaurar backups
        if backups_stash and (backups_stash / "backups").exists():
            try:
                backups_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(backups_stash / "backups", backups_dir, dirs_exist_ok=True)
            except Exception as e:
                report["errors"].append(f"backup_restore: {e}")
            finally:
                shutil.rmtree(backups_stash, ignore_errors=True)

        return report

    @classmethod
    def _install_assets(cls, deploy_dir: Path) -> Tuple[bool, str]:
        """Copia assets do projeto fonte (logo, icons, etc.) para o USERDIR de deploy."""
        try:
            from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
            source_assets = LiteXLPaths.get_template_dir().parent / "assets"
            if not source_assets.exists() or not source_assets.is_dir():
                return True, "Sem assets no projeto fonte (nada a copiar)"
            dest_doxoade = deploy_dir / ".doxoade"
            dest_assets = dest_doxoade / "assets"
            dest_assets.mkdir(parents=True, exist_ok=True)
            
            copied_files = 0
            copied_dirs = 0
            found_logo = None
            
            for item in source_assets.iterdir():
                try:
                    if item.is_file():
                        shutil.copy2(item, dest_assets / item.name)
                        copied_files += 1
                        if item.name in ("logo.ttf", "logo.otf", "logo.png", "logo2.png"):
                            found_logo = item.name
                    elif item.is_dir():
                        dest_sub = dest_assets / item.name
                        if dest_sub.exists():
                            shutil.rmtree(dest_sub, ignore_errors=True)
                        shutil.copytree(item, dest_sub)
                        copied_dirs += 1
                except Exception as e:
                    print(f"  {Fore.YELLOW}⚠ Falha ao copiar '{item.name}': {e}{Fore.RESET}")
            
            summary = f"{copied_files} arquivo(s)"
            if copied_dirs > 0:
                summary += f", {copied_dirs} diretório(s)"
            if found_logo:
                summary += f" | logo: {found_logo}"
            else:
                summary += " | logo: AUSENTE"
            
            return True, f"{summary} → {dest_assets}"
        except Exception as e:
            return False, f"Falha ao instalar assets: {e}"
        
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
        if mode == "production":
            try:
                return LiteXLEngine.get_user_dir()
            except Exception:
                return Path.home() / ".config" / "lite-xl"
        elif mode == "staging":                                    # ← NOVO
            from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
            return LiteXLPaths.get_staging_dir()                    # ← NOVO
        elif mode == "sandbox":
            try:
                return LiteXLEngine.get_sandbox_dir()
            except Exception:
                return Path.home() / ".config" / "lite-xl" / ".doxoade" / "sandbox"
        elif mode == "test":
            test_dir = Path.home() / ".config" / "lite-xl" / ".doxoade" / "test_deploy"
            try:
                test_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
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
        # Fase 1: "production" usa o novo sistema canonical (50 rotações, dedup)
        if mode == "production":
            return cls.create_canonical_backup(reason=reason)
        # Outros modos usam o sistema antigo
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
            cls._rotate_backups(backup_dir, max_backups=50)
            return True, backup_path
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao criar backup: {e}{Fore.RESET}")
            return False, None

    @classmethod
    def _rotate_backups(cls, backup_dir: Path, max_backups: int = 50):
        """Mantém apenas os 50 backups mais recentes (D3)."""
        try:
            backups = sorted(backup_dir.glob("init.lua.*.bak"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[max_backups:]:
                old_backup.unlink(missing_ok=True)
        except Exception:
            pass

    @classmethod
    def create_canonical_backup(cls, reason: str = "manual") -> Tuple[bool, Optional[Path]]:
        """Backup canonical com dedup por HASH (não filename) e rotação em 50."""
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        import hashlib
        canonical_init = LiteXLPaths.get_init_lua_path()
        if not canonical_init.exists():
            return True, None
        try:
            content_hash = hashlib.sha256(canonical_init.read_bytes()).hexdigest()[:8]
        except Exception:
            content_hash = "unknown"

        bkp_dir = LiteXLPaths.get_canonical_backups_dir()
        existing = sorted(bkp_dir.glob("init_*.lua.bak"),
                         key=lambda p: p.stat().st_mtime, reverse=True)

        # ✅ FIX 1: dedup por HASH do conteúdo, não por parts[2] (time)
        if existing and content_hash != "unknown":
            try:
                last_hash = hashlib.sha256(existing[0].read_bytes()).hexdigest()[:8]
                if last_hash == content_hash:
                    return True, existing[0]  # dedup OK
            except Exception:
                pass

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bkp_path = bkp_dir / f"init_{timestamp}_{content_hash}_{reason}.lua.bak"

        try:
            # ✅ FIX 5: copy (não copy2) para mtime = agora
            shutil.copy(canonical_init, bkp_path)
            cls._rotate_canonical_backups(max_backups=50)
            return True, bkp_path
        except Exception as e:
            print(f"{Fore.RED}✖ Falha no backup canonical: {e}{Fore.RESET}")
            return False, None

    @classmethod
    def _rotate_canonical_backups(cls, max_backups: int = 50):
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        bkp_dir = LiteXLPaths.get_canonical_backups_dir()
        backups = sorted(bkp_dir.glob("init_*.lua.bak"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[max_backups:]:
            try: old.unlink(missing_ok=True)
            except Exception: pass

    @classmethod
    def list_canonical_backups(cls) -> List[Path]:
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        bkp_dir = LiteXLPaths.get_canonical_backups_dir()
        return sorted(bkp_dir.glob("init_*.lua.bak"),
                     key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def rollback_canonical(cls, target_backup: Optional[Path] = None) -> Tuple[bool, str]:
        """Rollback reversível: backup do estado atual ANTES de restaurar."""
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        canonical_init = LiteXLPaths.get_user_dir() / ".doxoade" / "canonical_live" / "init.lua"
        canonical_init.parent.mkdir(parents=True, exist_ok=True)
        backups = cls.list_canonical_backups()
        if not backups:
            return False, "Nenhum backup canonical disponível."
        target = target_backup or backups[0]
        if not target.exists():
            return False, f"Backup não encontrado: {target}"
        cls.create_canonical_backup(reason="pre-rollback")
        try:
            shutil.copy2(target, canonical_init)
            cls.write_status_cache()   # ← HUD atualiza
            return True, f"Rollback concluído: {target.name}"
        except Exception as e:
            return False, f"Falha no rollback: {e}"

    @classmethod
    def get_canonical_status(cls) -> Dict[str, Any]:
        """Compara canonical vs staging vs test (D2: staging propaga ambos)."""
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        import hashlib

        def _fingerprint(p: Path) -> Dict[str, Any]:
            if not p.exists():
                return {"exists": False, "size": 0, "hash": None, "is_aot": False}
            raw = p.read_bytes()
            return {
                "exists": True,
                "size": len(raw),
                "hash": hashlib.sha256(raw).hexdigest()[:16],
                "is_aot": raw[:4].startswith(b"\x1bLua"),
            }

        canonical = _fingerprint(LiteXLPaths.get_init_lua_path())
        staging = _fingerprint(LiteXLPaths.get_staging_dir() / "init.lua")
        test = _fingerprint(
            cls._get_deploy_dir("test") / "init.lua"
        )

        promotion_pending = (
            staging["exists"] and canonical["hash"] is not None
            and staging["hash"] != canonical["hash"]
        )
        test_in_sync = (
            staging["exists"] and test["exists"]
            and staging["hash"] == test["hash"]
        )

        return {
            "canonical": canonical,
            "staging": staging,
            "test": test,
            "identical_canonical_staging": (
                canonical["hash"] == staging["hash"]
                and canonical["exists"] and staging["exists"]
            ),
            "promotion_pending": promotion_pending,
            "test_in_sync_with_staging": test_in_sync,
        }

    @classmethod
    def write_status_cache(cls) -> None:
        """Grava snapshot de status para HUD ler (Lua não pode chamar Python)."""
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        try:
            status = cls.get_canonical_status()
            status["updated_at"] = time.time()
            cache_path = LiteXLPaths.get_user_dir() / ".doxoade" / "diagnostics" / "canonical_status.json"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(status, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # silencioso — HUD é cosmético

    @classmethod
    def promote(cls, force: bool = False, allow_aot: bool = False) -> Tuple[bool, str]:
        """
        Promove staging → test + production (D2).
        - Backup canonical obrigatório ANTES (rigoroso, 50 rotações)
        - test NÃO recebe backup (playground)
        - AOT bloqueado por default (D4)
        """
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths

        staging_init = LiteXLPaths.get_staging_dir() / "init.lua"
        if not staging_init.exists():
            return False, "Staging não existe. Rode 'deploy staging' antes."

        status = cls.get_canonical_status()

        # D4: AOT bloqueado por default
        if status["staging"]["is_aot"] and not allow_aot and not force:
            return False, (
                "Staging é AOT bytecode. D4 despriorizou AOT. "
                "Use '--no-khonsu' no deploy staging, ou '--allow-aot' para forçar."
            )

        # Backup canonical (obrigatório)
        ok, bkp_path = cls.create_canonical_backup(reason="pre-promote")
        if not ok:
            return False, "Falha no backup canonical. Promote abortado."

        if ok and bkp_path:
            # Se dedup pegou (reason original ≠ pre-promote), avisar
            if "pre-promote" not in bkp_path.name:
                bkp_name = f"{bkp_path.name} (dedup — init idêntico ao último backup)"
            else:
                bkp_name = bkp_path.name
        else:
            bkp_name = "(sem backup)"

        # D2: propagar para test
        test_init = cls._get_deploy_dir("test") / "init.lua"
        test_init.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(staging_init, test_init)
        except Exception as e:
            return False, f"Falha ao promover para test: {e}"

        # 🏛️ 1. Atualiza a raiz (fallback para quem abrir o lite-xl.exe puro)
        canonical_root_init = LiteXLPaths.get_init_lua_path()
        try:
            shutil.copy2(staging_init, canonical_root_init)
        except Exception as e:
            return False, f"Falha ao promover para root: {e}"
            
        # 🏛️ 2. Atualiza o COFRE ISOLADO (Produção Real)
        canonical_live_dir = LiteXLPaths.get_user_dir() / ".doxoade" / "canonical_live"
        canonical_live_dir.mkdir(parents=True, exist_ok=True)
        canonical_live_init = canonical_live_dir / "init.lua"
        
        try:
            shutil.copy2(staging_init, canonical_live_init)
        except Exception as e:
            return False, f"Falha ao promover para canonical_live: {e}"
            
        cls.write_status_cache()   # ← atualizar HUD imediatamente
        bkp_name = bkp_path.name if bkp_path else "(sem backup — init não existia)"
        return True, (
            f"Propagado: staging → test + production\n"
            f"  💾 Backup canonical: {bkp_name}"
        )

    @classmethod
    def list_backups(cls, mode: DeployMode) -> list[Path]:
        # ✅ FIX 2: production usa o novo sistema canonical
        if mode == "production":
            return cls.list_canonical_backups()
        backup_dir = cls._get_backup_dir(mode)
        return sorted(backup_dir.glob("init.lua.*.bak"),
                     key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def restore_backup(cls, mode: DeployMode, backup_path: Optional[Path] = None) -> Tuple[bool, str]:
        # ✅ FIX 2b: production usa rollback canonical (reversível)
        if mode == "production":
            return cls.rollback_canonical(backup_path)
        # Sandbox / staging / test — lógica antiga
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
    def sterilize_environment(cls, deploy_dir: Path, keep_session: bool = True) -> None:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🧼 ESTERILIZANDO AMBIENTE ({deploy_dir.name})...{Style.RESET_ALL}")
        plugins_dir = deploy_dir / "plugins"
        plugins_disabled = deploy_dir / "plugins_DISABLED"
        if plugins_dir.exists() and plugins_dir.is_dir():
            try:
                if plugins_disabled.exists():
                    shutil.rmtree(plugins_disabled)
                plugins_dir.rename(plugins_disabled)
                print(f"  {Fore.YELLOW}⚠ Plugins nativos desativados (renomeados para plugins_DISABLED).{Fore.RESET}")
            except Exception as e:
                print(f"  {Fore.RED}✖ Falha ao desativar plugins: {e}{Fore.RESET}")
        user_settings = deploy_dir / "user_settings.lua"
        if user_settings.exists():
            try:
                disabled_settings = deploy_dir / "user_settings.lua.DISABLED"
                if disabled_settings.exists():
                    disabled_settings.unlink()
                user_settings.rename(disabled_settings)
                print(f"  {Fore.YELLOW}⚠ user_settings.lua desativado (soberano assumirá o controle).{Fore.RESET}")
            except Exception:
                try: user_settings.unlink()
                except Exception: pass
        trash_files = [
            "error.txt", "FATAL_CRASH_DUMP.txt", "init.lua.broken", 
            "init.lua.PROD_BACKUP", "session_log.txt.bak", "font_cache.lua",
            "user_settings.lua.bak",
        ]
        # ✅ Só apaga a sessão se NÃO for para manter
        if not keep_session:
            trash_files.extend(["session.lua", "session.json", "sovereign_session.lua"])

        ws_dir = deploy_dir / "workspace"
        if ws_dir.exists() and not keep_session:
            try:
                shutil.rmtree(ws_dir)
                print(f"  {Fore.YELLOW}⚠ Workspace removido (evita restauração de state poluído).{Fore.RESET}")
            except Exception:
                pass
                
        for fname in trash_files:
            fpath = deploy_dir / fname
            if fpath.exists():
                try: fpath.unlink()
                except Exception: pass
        dox_dir = deploy_dir / ".doxoade"
        if dox_dir.exists():
            old_assets = dox_dir / "assets"
            if old_assets.exists() and old_assets.is_dir():
                try:
                    shutil.rmtree(old_assets, ignore_errors=True)
                except Exception:
                    pass
            for sub in ["api_guard", "diagnostics", "canvas_cache", "terminal_temp"]:
                target = dox_dir / sub
                if target.exists() and target.is_dir():
                    try:
                        shutil.rmtree(target)
                        target.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass
            for pty_dir in dox_dir.glob("terminal_pty_ipc*"):
                if pty_dir.is_dir():
                    try: shutil.rmtree(pty_dir)
                    except Exception: pass
            for f in dox_dir.glob("*.ndjson*"):
                try: f.unlink()
                except Exception: pass
            for f in dox_dir.glob("*.stderr"):
                try: f.unlink()
                except Exception: pass
            for f in dox_dir.glob("*.tmp"):
                try: f.unlink()
                except Exception: pass
        print(f"  {Fore.GREEN}✔ Ambiente esterilizado com sucesso. Caches e IPCs limpos.{Fore.RESET}\n")

    @classmethod
    def deploy(
        cls,
        mode: DeployMode = "production",
        force: bool = False,
        no_khonsu: bool = True,                # ← D4: AOT abandonado como default
    ) -> Dict[str, Any]:

        # 🔧 AUTO-ELEVAÇÃO: se não for Admin e for Windows, relança elevado
        import sys, os
        # 🛑 BYPASS DO KHONSU ATIVADO (Texto puro sem AOT)
        if sys.platform == "win32" and mode in ("test", "sandbox"):
            try:
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                from doxoade.tools.error_info import formated_traceback
                formated_traceback(e, "Deploy Elevarion Fail")
                is_admin = False

            if not is_admin and not os.environ.get("DOXOADE_ELEVATED"):
                print(f"{Fore.YELLOW}🔐 [TYPHON] Sem privilégios de Admin. Solicitando elevação via UAC...{Fore.RESET}")
                try:
                    import subprocess
                    # Reexecuta o comando com elevação
                    python_exe = sys.executable
                    module = "doxoade"
                    args = sys.argv[1:]
                    cmd_str = f'"{python_exe}" -m {module} ' + " ".join(f'"{a}"' if ' ' in a else a for a in args)
                    # Passa DOXOADE_ELEVATED=1 para evitar loop infinito
                    env_block = f"set DOXOADE_ELEVATED=1 && {cmd_str}"
                    subprocess.Popen(
                        ["powershell", "-Command", f'Start-Process cmd -ArgumentList "/k {env_block}" -Verb RunAs'],
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                    )
                    print(f"{Fore.GREEN}✔ Janela elevada aberta. Deploy continua no console Admin.{Fore.RESET}")
                    print(f"{Fore.LIGHTBLACK_EX}   Feche este console após o deploy elevar.{Fore.RESET}")
                    return {"success": False, "error": "elevation_requested", "backup": None}
                except Exception as e:
                    print(f"{Fore.RED}✖ Falha na elevação: {e}{Fore.RESET}")
                    return {"success": False, "error": str(e), "backup": None}

        # ─── Resto do deploy original ───
        deploy_dir = cls._get_deploy_dir(mode)
        if deploy_dir is None:
            # 🛡️ [FASE 5] Fallback: força criação do diretório padrão
            home = Path.home()
            if mode == "production":
                deploy_dir = home / ".config" / "lite-xl"
            elif mode == "test":
                deploy_dir = home / ".config" / "lite-xl" / ".doxoade" / "test_deploy"
            elif mode == "sandbox":
                deploy_dir = home / ".config" / "lite-xl" / ".doxoade" / "sandbox"
            else:
                return {"success": False, "error": f"Modo inválido: {mode}", "backup": None}
        
        try:
            deploy_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"success": False, "error": f"Falha ao criar diretório {deploy_dir}: {e}", "backup": None}
        
        
        # 🧼 FASE DE ESTERILIZAÇÃO AUTOMÁTICA (Limpa caches, IPCs e plugins conflitantes)
        if mode in ("production", "test"):
            #cls.sterilize_environment(deploy_dir)
            cls.sterilize_environment(deploy_dir, keep_session=(mode == "production"))

        # dentro de deploy(), logo após sterilize_environment
        # ok_assets, msg_assets = cls._install_assets(deploy_dir)
        # print(f"  {Fore.WHITE}6. Assets:{Fore.RESET} {msg_assets}")
        # if not ok_assets and not force:
        #     return {"success": False, "error": msg_assets, "backup": backup_path}
            
        backup_path = None

        # Âncora do Interpretador Python: grava o executável do venv ativo
        # para que todos os templates Lua (consult, pty, linters) saibam exatamente quem chamar
        dox_dir = deploy_dir / ".doxoade"
        dox_dir.mkdir(parents=True, exist_ok=True)
        (dox_dir / "python_path.txt").write_text(str(Path(sys.executable).resolve()), encoding="utf-8")
        
        home_anchor = Path.home() / ".doxoade" / "python_path.txt"
        home_anchor.parent.mkdir(parents=True, exist_ok=True)
        home_anchor.write_text(str(Path(sys.executable).resolve()), encoding="utf-8")

        if mode == "test":
            for art in ["session_log.txt", "error.txt"]:
                target = deploy_dir / art
                if target.exists():
                    try: target.unlink()
                    except Exception: pass

        # 🔧 [FASE 1.5] Instalar assets (chamar apenas UMA vez, fora de loops)
        # ok_assets, msg_assets = cls._install_assets(deploy_dir)
        # print(f"  {Fore.WHITE}6. Assets:{Fore.RESET} {msg_assets}")
        # if not ok_assets and not force:
        #     return {"success": False, "error": msg_assets, "backup": backup_path}

        if mode == "production":
            # Fase 1: backup canonical obrigatório ANTES de qualquer escrita
            ok, backup_path = cls.create_canonical_backup(reason="pre-deploy")
            if not ok and not force:
                return {"success": False,
                        "error": "Falha no backup canonical",
                        "backup": None}

        # if gate_res["success"] and gate_res.get("bytecode"):
        #     init_dest.write_bytes(gate_res["bytecode"])
        #     installed_size = len(gate_res["bytecode"])
        #     opt_mode = "bytecode"

        # 🔧 [FASE 1] Instalar assets (logo, icons) no deploy_dir
        ok_assets, msg_assets = cls._install_assets(deploy_dir)
        print(f"  {Fore.WHITE}6. Assets:{Fore.RESET} {msg_assets}")
        if not ok_assets and not force:
            return {"success": False, "error": msg_assets, "backup": backup_path}

        try:
            py_anchor = deploy_dir / ".doxoade" / "python_path.txt"
            py_anchor.parent.mkdir(parents=True, exist_ok=True)
            py_anchor.write_text(sys.executable, encoding="utf-8")

            init_dest = deploy_dir / "init.lua"

            templates = LiteXLInitBuilder.get_template_files()
            unified_source, source_map = DoxlyKhonsuGate.assemble_unified_buffer(templates, mode=mode)

            # 🛑 BYPASS DO KHONSU ATIVADO (Texto puro sem AOT)
            if no_khonsu:
                init_dest.write_text(unified_source, encoding="utf-8")
                installed_size = len(unified_source)
                opt_mode = "plain_no_khonsu"
            else:
                gate_res = DoxlyKhonsuGate.compile_aot_supervisioned(target_mode=mode, verbose=True)
                print(f"  {Fore.WHITE}5. Khonsu Gate:{Fore.RESET}")
                print(f"     • Success: {gate_res.get('success', False)}")
                print(f"     • Bytecode: {'SIM (' + str(len(gate_res.get('bytecode', b''))) + ' bytes)' if gate_res.get('bytecode') else 'NÃO'}")
                print(f"     • Opt Mode: {gate_res.get('opt_mode', 'N/A')}")
                print(f"     • Erro: {gate_res.get('error', 'Nenhum')}")

                if not gate_res["success"]:
                    if not force:
                        print(f"\n{Fore.RED}{Style.BRIGHT}✖ COMPILAÇÃO AOT FALHOU. DEPLOY ABORTADO.{Style.RESET_ALL}")
                        return {"success": False, "error": gate_res.get('error', 'AOT Failed'), "backup": backup_path}
                    else:
                        print(f"\n{Fore.YELLOW}⚠ --force ativo. Continuando com fallback plain.{Fore.RESET}")

                if gate_res["success"] and gate_res.get("bytecode"):
                    init_dest.write_bytes(gate_res["bytecode"])
                    installed_size = len(gate_res["bytecode"])
                    opt_mode = gate_res.get("opt_mode", "bytecode")
                else:
                    init_dest.write_text(gate_res.get("source", unified_source), encoding="utf-8")
                    installed_size = len(gate_res.get("source", unified_source))
                    opt_mode = "plain_fallback"
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
        finally:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 DIAGNÓSTICO DE DEPLOY — [{mode.upper()}]{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}1. Diretório de Deploy:{Fore.RESET} {deploy_dir}")
            print(f"  {Fore.WHITE}2. Python:{Fore.RESET} {sys.executable}")
            print(f"  {Fore.WHITE}3. Templates:{Fore.RESET} {len(LiteXLInitBuilder.get_template_files())} arquivos")
            print(f"  {Fore.WHITE}4. Khonsu:{Fore.RESET} {'DESATIVADO' if no_khonsu else 'ATIVADO'}")
            # 🔧 [FASE 1] linha nova
            assets_dir = deploy_dir / ".doxoade" / "assets"
            if assets_dir.exists():
                assets_count = sum(1 for _ in assets_dir.rglob("*") if _.is_file())
                print(f"  {Fore.WHITE}5. Assets:{Fore.RESET} {assets_count} arquivo(s) em .doxoade/assets/")
            else:
                print(f"  {Fore.WHITE}5. Assets:{Fore.RESET} {Fore.YELLOW}ausentes (fallback){Fore.RESET}")
            print()

            import hashlib
            import json

            unified_source, _ = DoxlyKhonsuGate.assemble_unified_buffer(templates, mode=mode)
            build_meta = {
                "mode": mode,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "aot": not no_khonsu,
                "fingerprint": hashlib.sha256(unified_source.encode("utf-8")).hexdigest()[:16],
                "templates_count": len(templates),
                "templates": [t.name for t in templates],
            }
            diag_dir = deploy_dir / ".doxoade" / "diagnostics"
            diag_dir.mkdir(parents=True, exist_ok=True)
            (diag_dir / f"last_build_{mode}.json").write_text(
                json.dumps(build_meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print()
            # ✅ Fase 3: atualizar cache para HUD
            cls.write_status_cache()

    @classmethod
    def print_status(cls, mode: Optional[DeployMode] = None) -> None:
        # ✅ FIX Fase 2: staging incluído
        modes = [mode] if mode else ["production", "staging", "sandbox", "test"]
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🐉 TYPHON DEPLOY STATUS{Style.RESET_ALL}\n")

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

    @classmethod
    def _sync_cofre_infra(cls, real_dir: Path, target_dir: Path) -> None:
        """Infra mínima p/ o cofre. Tolerante a locks; nunca src==dest; sem forensics stale."""
        src_dox = real_dir / ".doxoade"
        dst_dox = target_dir / ".doxoade"
        dst_dox.mkdir(parents=True, exist_ok=True)
        if not src_dox.exists():
            return
        SKIP_DIRS = {"canonical_live", "backups", "staging", "test_deploy",
                     "sandbox", "api_guard", "diagnostics", "shadow_harness",
                     "canvas_cache", "terminal_temp"}
        skipped = 0
        for item in src_dox.iterdir():
            if item.name in SKIP_DIRS or item.name.startswith("terminal_pty_ipc"):
                continue
            try:
                if item.is_dir():
                    shutil.copytree(item, dst_dox / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst_dox / item.name)
            except Exception:
                skipped += 1
        try:
            st = src_dox / "diagnostics" / "canonical_status.json"
            if st.exists():
                (dst_dox / "diagnostics").mkdir(parents=True, exist_ok=True)
                shutil.copy2(st, dst_dox / "diagnostics" / "canonical_status.json")
        except Exception:
            skipped += 1
        for fname in ("sovereign_session.lua",):
            s, d = src_dox / fname, dst_dox / fname
            if s.exists() and not d.exists():
                try: shutil.copy2(s, d)
                except Exception: pass
        for fname in ("session.lua", "session.json"):
            s, d = real_dir / fname, target_dir / fname
            if s.exists() and not d.exists():
                try: shutil.copy2(s, d)
                except Exception: pass
        ws_s, ws_d = real_dir / "workspace", target_dir / "workspace"
        if ws_s.exists() and not ws_d.exists():
            try: shutil.copytree(ws_s, ws_d, dirs_exist_ok=True)
            except Exception: pass
        if skipped:
            print(f"{Fore.YELLOW}  ⚠ {skipped} item(ns) de infra ignorado(s) (em uso/lock).{Fore.RESET}")


    # ═══════════════════════════════════════════════════════════
    # 🧪 LANÇAMENTO COM ISOLAMENTO
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def launch(cls, mode: DeployMode = "production", exorcise: bool = True, raw_mode: bool = False) -> Optional[int]:
        real_deploy_dir = cls._get_deploy_dir(mode)
        target_deploy_dir = real_deploy_dir
        if mode == "production" and not raw_mode:
            target_deploy_dir = real_deploy_dir / ".doxoade" / "canonical_live"
            target_deploy_dir.mkdir(parents=True, exist_ok=True)
            staging_init = real_deploy_dir / ".doxoade" / "staging" / "init.lua"
            src_init = staging_init if staging_init.exists() else (real_deploy_dir / "init.lua")
            if src_init.exists():
                try:
                    shutil.copy2(src_init, target_deploy_dir / "init.lua")
                except Exception as e:
                    print(f"{Fore.YELLOW}  ⚠ init do cofre não sincronizado: {e}{Fore.RESET}")
            cls._sync_cofre_infra(real_deploy_dir, target_deploy_dir)
        if exorcise:
            ipc_queue = target_deploy_dir / ".ipc_queue"
            try:
                with open(ipc_queue, "a", encoding="utf-8") as f:
                    f.write("__DOXOADE_GRACEFUL_QUIT__\n")
                time.sleep(1.5)
            except Exception:
                pass
            pid_file = target_deploy_dir / f".{mode}.pid"
            if pid_file.exists():
                try:
                    old_pid = int(pid_file.read_text().strip())
                    if is_pid_alive(old_pid):
                        if sys.platform == "win32":
                            subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
                        else:
                            os.kill(old_pid, 9)
                        time.sleep(0.4)
                    pid_file.unlink(missing_ok=True)
                except Exception:
                    pass
        exe = LiteXLEngine.find_executable()
        if not exe:
            print(f"{Fore.RED}✖ Executável do Lite XL não encontrado no sistema.{Fore.RESET}")
            return None
        env = os.environ.copy()
        env["LITE_USERDIR"] = str(target_deploy_dir)
        env["XDG_CONFIG_HOME"] = str(target_deploy_dir.parent)
        env["DOXOADE_DEPLOY_MODE"] = mode
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 DIAGNÓSTICO DE LAUNCH — [{mode.upper()}]{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}1. Deploy Dir:{Fore.RESET} {target_deploy_dir}")
        if mode == "production" and not raw_mode:
            print(f"  {Fore.GREEN}2. ISOLAMENTO ATIVO:{Fore.RESET} sessão protegida em canonical_live")
        print(f"  {Fore.WHITE}3. LITE_USERDIR:{Fore.RESET} {env['LITE_USERDIR']}")
        print(f"  {Fore.WHITE}4. DOXOADE_DEPLOY_MODE:{Fore.RESET} {mode}\n")
        try:
            CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
            proc = subprocess.Popen([str(exe)], env=env, creationflags=CREATE_NEW_CONSOLE)
            pid = proc.pid
            (target_deploy_dir / f".{mode}.pid").write_text(str(pid), encoding="utf-8")
            print(f"{Fore.CYAN}🚀 Lite XL ({mode.upper()}) iniciado com sucesso.{Fore.RESET}")
            return pid
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao lançar processo: {e}{Fore.RESET}")
            return None

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

    @classmethod
    def _acquire_mode_lock(cls, mode: DeployMode) -> bool:
        lock_file = cls._get_deploy_dir(mode) / ".deploy.lock"
        if lock_file.exists():
            try:
                pid = int(lock_file.read_text().strip())
                if is_pid_alive(pid):
                    print(f"{Fore.RED}✖ Deploy '{mode}' bloqueado: PID {pid} ainda rodando.{Fore.RESET}")
                    return False
            except Exception:
                pass
        lock_file.write_text(str(os.getpid()))
        return True

    @classmethod
    def _release_mode_lock(cls, mode: DeployMode) -> None:
        lock_file = cls._get_deploy_dir(mode) / ".deploy.lock"
        try: lock_file.unlink()
        except Exception: pass
