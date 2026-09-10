# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_deploy.py
"""
🐉 TYPHON DEPLOY ENGINE v2.1 — Pipeline de Deploy com Separação Produção/Testes.
Modos: PRODUCTION (com backup), SANDBOX (isolado), TEST (chaos injection).

V2.1 — ÁRTEMIS HOOK V1.2 (apêndice module-level no FINAL do arquivo, indent 0):
    Pré-geração automática de thumbnails binárias (.thumb.rlebin) antes do AOT.
    Plano A: wrapper delega a _pre_generate_thumbnails + deploy canônico.
    Plano B: falha de thumbnail é logada e o deploy prossegue (best-effort).
    Plano C: remover o bloco contíguo do apêndice restaura o pristine (1 delete).
    Origem: corrige o NameError:395 (bloco colado no corpo da classe) — ProDeNov 1.2.1/5.1.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Literal

from doxoade.tools.doxcolors import Fore, Style
from .engine_lite_xl import LiteXLEngine
from .lite_xl_init_builder import LiteXLInitBuilder
from .typhon_doxly.doxly_khonsu_gate import DoxlyKhonsuGate

DeployMode = Literal["production", "sandbox", "test"]


class TyphonDeployEngine:
    """Motor de Deploy com 3 modos: PRODUCTION, SANDBOX, TEST."""

    # ═══════════════════════════════════════════════════════════
    # 📂 RESOLUÇÃO DE CAMINHOS POR MODO
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def _get_deploy_dir(cls, mode: DeployMode) -> Path:
        """Retorna o diretório alvo baseado no modo."""
        if mode == "production":
            return LiteXLEngine.get_user_dir()
        elif mode == "sandbox":
            return LiteXLEngine.get_sandbox_dir()
        elif mode == "test":
            test_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
            test_dir.mkdir(parents=True, exist_ok=True)
            return test_dir
        else:
            raise ValueError(f"Modo inválido: {mode}")

    @classmethod
    def _get_backup_dir(cls, mode: DeployMode) -> Path:
        """Retorna o diretório de backups."""
        if mode == "production":
            bkp_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "backups" / "production"
        elif mode == "sandbox":
            bkp_dir = LiteXLEngine.get_sandbox_dir() / ".backups"
        else:
            bkp_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "backups" / "test"
        bkp_dir.mkdir(parents=True, exist_ok=True)
        return bkp_dir

    # ═══════════════════════════════════════════════════════════
    # 💾 SISTEMA DE BACKUP COM TIMESTAMPS
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def create_backup(cls, mode: DeployMode, reason: str = "pre-deploy") -> Tuple[bool, Optional[Path]]:
        """Cria backup timestampado do init.lua atual."""
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
        """Remove backups antigos, mantendo apenas os N mais recentes."""
        try:
            backups = sorted(backup_dir.glob("init.lua.*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[max_backups:]:
                old_backup.unlink()
        except Exception:
            pass

    @classmethod
    def list_backups(cls, mode: DeployMode) -> list[Path]:
        """Lista todos os backups disponíveis."""
        backup_dir = cls._get_backup_dir(mode)
        return sorted(backup_dir.glob("init.lua.*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def restore_backup(cls, mode: DeployMode, backup_path: Optional[Path] = None) -> Tuple[bool, str]:
        """Restaura um backup específico ou o mais recente."""
        try:
            deploy_dir = cls._get_deploy_dir(mode)
            init_path = deploy_dir / "init.lua"
            if backup_path is None:
                backups = cls.list_backups(mode)
                if not backups:
                    return False, "Nenhum backup encontrado"
                backup_path = backups[0]
            if not backup_path.exists():
                return False, f"Backup não encontrado: {backup_path}"
            if init_path.exists():
                cls.create_backup(mode, reason="pre-restore")
            shutil.copy2(backup_path, init_path)
            return True, f"Backup restaurado: {backup_path.name}"
        except Exception as e:
            return False, f"Falha ao restaurar: {e}"

    # ═══════════════════════════════════════════════════════════
    # 🔪 EXORCISMO DE PROCESSOS (RESTAURADO V2.1 — launch production + CLI)
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def exorcise_instances(cls, wait_seconds: float = 1.5) -> bool:
        """🕊️ Quit gracioso (salva sessão) + 🔪 hard kill de fantasmas."""
        try:
            from .lite_xl_process import LiteXLProcess
            if LiteXLProcess.is_process_alive():
                try:
                    LiteXLProcess.send_to_running_instance("__DOXOADE_GRACEFUL_QUIT__")
                except Exception:
                    pass
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    if not LiteXLProcess.is_process_alive():
                        break
                    time.sleep(0.1)
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"],
                               capture_output=True, timeout=5)
            else:
                subprocess.run(["pkill", "-f", "lite-xl"],
                               capture_output=True, timeout=5)
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Exorcismo parcial: {e}{Fore.RESET}")
            return False

    @classmethod
    def exorcise_mode_instance(cls, mode: DeployMode) -> None:
        """Encerra apenas o processo isolado do modo especificado (sem tocar na produção)."""
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

    # ═══════════════════════════════════════════════════════════
    # 🚀 DEPLOY POR MODO (CANÔNICO — o apêndice ÁRTEMIS o envolve)
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def deploy(cls, mode: DeployMode = "production", force: bool = False) -> Dict[str, Any]:
        """Compila e instala o init.lua supervisionado pelo Khonsu Gatekeeper."""
        deploy_dir = cls._get_deploy_dir(mode)
        deploy_dir.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if mode == "test":
            session_log = deploy_dir / "session_log.txt"
            error_txt = deploy_dir / "error.txt"
            if session_log.exists():
                try: session_log.unlink()
                except Exception: pass
            if error_txt.exists():
                try: error_txt.unlink()
                except Exception: pass
        if mode == "production":
            ok, backup_path = cls.create_backup(mode, reason="pre-deploy")
            if not ok and not force:
                return {"success": False, "error": "Falha ao criar backup de segurança", "backup": None}
        try:
            py_anchor = deploy_dir / ".doxoade" / "python_path.txt"
            py_anchor.parent.mkdir(parents=True, exist_ok=True)
            py_anchor.write_text(sys.executable, encoding="utf-8")
            gate_res = DoxlyKhonsuGate.compile_aot_supervisioned(target_mode=mode, verbose=True)
            init_dest = deploy_dir / "init.lua"
            if gate_res["success"] and gate_res["bytecode"]:
                init_dest.write_bytes(gate_res["bytecode"])
                installed_size = len(gate_res["bytecode"])
            else:
                init_dest.write_text(gate_res["source"], encoding="utf-8")
                installed_size = len(gate_res["source"])
            return {
                "success": True,
                "mode": mode,
                "init": init_dest,
                "backup": backup_path,
                "size": installed_size,
                "opt_mode": gate_res["opt_mode"],
                "error": gate_res.get("error"),
            }
        except Exception as e:
            if mode == "production" and backup_path and backup_path.exists():
                init_dest = deploy_dir / "init.lua"
                shutil.copy2(backup_path, init_dest)
            return {"success": False, "error": str(e), "backup": backup_path}

    # ═══════════════════════════════════════════════════════════
    # 🖼️ ÁRTEMIS — PRÉ-GERAÇÃO DE THUMBNAILS (delegada pelo apêndice)
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def _pre_generate_thumbnails(cls, project_root: Optional[Any] = None) -> int:
        """Gera thumbnails para todas as imagens do projeto (Plano A automático)."""
        try:
            from doxoade.tools.image_systems.image_manager import ImageAssetManager
            if isinstance(project_root, (str, Path)):
                root = Path(project_root).resolve()
            else:
                root = Path(os.getcwd()).resolve()
            report = ImageAssetManager.sync_project_thumbnails(root, force=False)
            if isinstance(report, dict):
                generated = report.get("generated", 0)
                hits = report.get("cache_hits", 0)
                total = report.get("total_scanned", 0)
                if total > 0:
                    print(f"{Fore.GREEN}✔ [ÁRTEMIS] {total} imagens verificadas ({generated} geradas, {hits} em cache).{Fore.RESET}")
                return generated
            return 0
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ [ÁRTEMIS] Thumbnails skip: {e}{Fore.RESET}")
            return 0

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
                [str(exe), os.getcwd()],
                env=env,
                creationflags=CREATE_NEW_CONSOLE,
                close_fds=(sys.platform != "win32")
            )
            (deploy_dir / f".{mode}.pid").write_text(str(proc.pid))
            print(f"{Fore.GREEN}✔ Lite XL ({mode.upper()}) iniciado com sucesso (PID: {proc.pid}){Fore.RESET}")
            return True
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


# ═══════════════════════════════════════════════════════════
# 🖼️ ÁRTEMIS HOOK V1.2 — wrapper module-level (APÓS a classe, indent 0)
# Plano A: delega a _pre_generate_thumbnails + deploy canônico.
# Plano B: exceções contidas; o deploy é soberano.
# Plano C: remover este bloco contíguo restaura o pristine (1 delete).
# ═══════════════════════════════════════════════════════════
_ORIGINAL_DEPLOY = TyphonDeployEngine.deploy


@classmethod
def _deploy_with_thumbnails(cls, mode: DeployMode = "production", force: bool = False) -> Dict[str, Any]:
    """Pré-gera sidecars .thumb.rlebin (Plano A) e delega ao deploy canônico."""
    try:
        from doxoade.tools.image_systems import ThumbnailEngine
        project_root = Path.cwd()
        engine = ThumbnailEngine(project_root)
        images = engine.scan(project_root / ".doxoade" / "assets" / "images", recursive=True)
        if images:
            print(f"{Fore.CYAN}🖼️ [ÁRTEMIS] Pré-gerando {len(images)} thumbnails binárias...{Fore.RESET}")
            results = engine.batch(images, preset="card")
            # Correção: results é lista de dicts, usar ['ok'] em vez de .ok
            ok_count = sum(1 for r in results if r.get('ok', False))
            pend_count = sum(1 for r in results if r.get('status') == 'pending')
            print(f"{Fore.GREEN}  ✔ {ok_count}/{len(images)} sidecars prontos{Fore.RESET}"
                  + (f" | {Fore.YELLOW}⏳ {pend_count} pending (Pillow ausente?){Fore.RESET}" if pend_count else ""))
    except Exception as e:
        print(f"{Fore.YELLOW}⚠ [ÁRTEMIS] Thumbnails skip: {type(e).__name__}: {e}{Fore.RESET}")
    return _ORIGINAL_DEPLOY(mode, force=force)


TyphonDeployEngine.deploy = classmethod(_deploy_with_thumbnails)
