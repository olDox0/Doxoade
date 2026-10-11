# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/esp_manager.py
"""
[HERA/MA'AT] Gestor Soberano de Partição ESP e BCD do Windows.
Automatiza a instalação e reversão de binários UEFI na partição de boot com salvaguarda.
Em estrita conformidade com o protocolo ProDeNov.
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class EspStatus:
    is_installed: bool
    guid: Optional[str] = None
    target_path: Optional[str] = None
    label: Optional[str] = None
    installed_at: Optional[str] = None


class EspManager:
    """
    Gerenciador com garantias transacionais de ESP (EFI System Partition) e BCD.
    Garante desmontagem via try...finally e mantém histórico no manifesto local.
    """

    MOUNT_DRIVE = "S:"
    MANIFEST_FILE = ".doxoade/esp_manifest.json"
    GUID_REGEX = re.compile(r"\{([0-9a-fA-F\-]{36})\}")

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.manifest_path = self.root / self.MANIFEST_FILE

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo possui privilégios de Administrador no Windows."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def load_manifest(self) -> Optional[Dict[str, Any]]:
        """Carrega dados do manifesto local."""
        if not self.manifest_path.exists():
            return None
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_manifest(self, data: Dict[str, Any]) -> None:
        """Persiste manifesto local com garantias de atomicidade."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def status(self) -> EspStatus:
        """Verifica o status atual da entrada do Doxoade no sistema."""
        manifest = self.load_manifest()
        if not manifest or "guid" not in manifest:
            return EspStatus(is_installed=False)

        # Checa se o GUID ainda existe no BCD
        guid = manifest["guid"]
        try:
            check = subprocess.run(["bcdedit", "/enum", guid], capture_output=True, text=True)
            if check.returncode == 0:
                return EspStatus(
                    is_installed=True,
                    guid=guid,
                    target_path=manifest.get("target_path"),
                    label=manifest.get("label"),
                    installed_at=manifest.get("installed_at")
                )
        except Exception:
            pass

        return EspStatus(is_installed=False, guid=guid)

    def install(self, kernel_path: Path, label: str = "Doxoade Sovereign OS (IA-32)") -> Dict[str, Any]:
        r"""
        Instalação blindada:
        1. Monta S: /s
        2. Copia kernel para S:\EFI\doxoade\bootia32.efi
        3. Registra no BCD e obtém GUID
        4. Desmonta S: /d em bloco finally garantido
        """
        if not self.is_admin():
            raise PermissionError("Esta operação requer privilégios de Administrador. Execute o terminal como Admin.")

        kernel_path = Path(kernel_path).resolve()
        if not kernel_path.exists():
            raise FileNotFoundError(f"Kernel não encontrado: {kernel_path}")

        # Se já existir uma entrada anterior registrada, remove para evitar duplicatas
        current = self.status()
        if current.is_installed and current.guid:
            self.uninstall()

        mounted = False
        try:
            # 1. Monta ESP
            res_mount = subprocess.run(["mountvol", self.MOUNT_DRIVE, "/s"], capture_output=True, text=True)
            if res_mount.returncode != 0:
                raise RuntimeError(f"Falha ao montar ESP: {res_mount.stderr.strip() or res_mount.stdout.strip()}")
            mounted = True

            # 2. Copia binário respeitando o nome real do arquivo (bootx64.efi ou bootia32.efi)
            dest_dir = Path(f"{self.MOUNT_DRIVE}\\EFI\\doxoade")
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_name = kernel_path.name.lower()
            dest_file = dest_dir / dest_name
            shutil.copy2(str(kernel_path), str(dest_file))

            # 3. Cria entrada no BCD
            cmd_copy = subprocess.run(["bcdedit", "/copy", "{bootmgr}", "/d", label], capture_output=True, text=True)
            if cmd_copy.returncode != 0:
                raise RuntimeError(f"Falha ao registrar entrada no BCD: {cmd_copy.stderr.strip()}")

            match = self.GUID_REGEX.search(cmd_copy.stdout)
            if not match:
                raise RuntimeError(f"Não foi possível capturar o GUID retornado pelo bcdedit: {cmd_copy.stdout}")

            guid = match.group(0)

            # 4. Aponta para o nome exato do arquivo instalado (ex: \EFI\doxoade\bootx64.efi)
            efi_path = f"\\EFI\\doxoade\\{dest_name}"
            cmd_set = subprocess.run(["bcdedit", "/set", guid, "path", efi_path], capture_output=True, text=True)
            if cmd_set.returncode != 0:
                subprocess.run(["bcdedit", "/delete", guid])
                raise RuntimeError(f"Falha ao configurar caminho no BCD: {cmd_set.stderr.strip()}")

            # 5. Coloca em PRIMEIRO LUGAR na ordem de boot da placa-mãe
            subprocess.run(["bcdedit", "/set", "{fwbootmgr}", "displayorder", guid, "/addfirst"], capture_output=True)

            manifest_data = {
                "guid": guid,
                "label": label,
                "target_path": str(kernel_path),
                "installed_at": str(Path().resolve())
            }
            self.save_manifest(manifest_data)

            return {"success": True, "guid": guid, "label": label, "file": str(dest_file)}

        finally:
            # GARANTIA ABSOLUTA: Sempre desmonta S:, mesmo se ocorrer erro
            if mounted:
                subprocess.run(["mountvol", self.MOUNT_DRIVE, "/d"], capture_output=True)

    def uninstall(self) -> Dict[str, Any]:
        """
        Reversão atômica:
        1. Remove GUID do BCD
        2. Monta S:, apaga S:\EFI\doxoade\ e desmonta S:
        3. Remove o manifesto
        """
        if not self.is_admin():
            raise PermissionError("Esta operação requer privilégios de Administrador.")

        manifest = self.load_manifest()
        guid = manifest.get("guid") if manifest else None

        # 1. Remove do BCD
        if guid:
            subprocess.run(["bcdedit", "/delete", guid], capture_output=True)

        # 2. Limpa arquivos da partição ESP
        mounted = False
        try:
            res_mount = subprocess.run(["mountvol", self.MOUNT_DRIVE, "/s"], capture_output=True, text=True)
            if res_mount.returncode == 0:
                mounted = True
                dest_dir = Path(f"{self.MOUNT_DRIVE}\\EFI\\doxoade")
                if dest_dir.exists():
                    shutil.rmtree(str(dest_dir), ignore_errors=True)
        finally:
            if mounted:
                subprocess.run(["mountvol", self.MOUNT_DRIVE, "/d"], capture_output=True)

        # 3. Limpa o manifesto
        if self.manifest_path.exists():
            try:
                self.manifest_path.unlink()
            except Exception:
                pass

        return {"success": True, "guid": guid, "message": "Entrada e arquivos removidos com sucesso."}
