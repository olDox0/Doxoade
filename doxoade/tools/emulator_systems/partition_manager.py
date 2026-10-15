# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/partition_manager.py
"""
[MA'AT/HERA] Gestor Atômico e Seguro de Partições do Windows.
Automatiza a redução segura de C: e criação da partição FAT32 para o Micro-OS.
Em estrita conformidade com o protocolo ProDeNov v2.0.
"""

import ctypes
import json
import subprocess
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class PartitionAudit:
    drive_letter: str
    current_size_gb: float
    free_space_gb: float
    min_size_gb: float
    can_shrink_1gb: bool
    drive_m_available: bool


class PartitionManager:
    """Gerenciador seguro de fatias de disco via PowerShell Storage API."""

    TARGET_LETTER = "M"
    TARGET_LABEL = "ALPINE"
    MIN_WINDOWS_FREE_MB = 1800  # Trava de segurança: C: não pode ficar abaixo disso

    @staticmethod
    def is_admin() -> bool:
        """Verifica privilégios de Administrador."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @classmethod
    def audit(cls) -> PartitionAudit:
        """Audita C: e verifica se é seguro encolher 1 GB."""
        ps_cmd = (
            "$part = Get-Partition -DriveLetter C; "
            "$vol = Get-Volume -DriveLetter C; "
            "$supp = Get-PartitionSupportedSize -DriveLetter C; "
            "$m_used = Get-Volume -DriveLetter M -ErrorAction SilentlyContinue; "
            "@{ "
            "CurrentSize = $part.Size; "
            "FreeSpace = $vol.SizeRemaining; "
            "SizeMin = $supp.SizeMin; "
            "DriveMAvailable = ($m_used -eq $null) "
            "} | ConvertTo-Json"
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Falha ao auditar partições: {res.stderr.strip()}")

        data = json.loads(res.stdout)
        current_gb = data["CurrentSize"] / (1024**3)
        free_gb = data["FreeSpace"] / (1024**3)
        min_gb = data["SizeMin"] / (1024**3)

        # Só permite encolher 1 GB se o espaço livre restante for maior que a trava
        remaining_free_mb = (data["FreeSpace"] - (1024**3)) / (1024**2)
        can_shrink = remaining_free_mb >= cls.MIN_WINDOWS_FREE_MB

        return PartitionAudit(
            drive_letter="C",
            current_size_gb=round(current_gb, 2),
            free_space_gb=round(free_gb, 2),
            min_size_gb=round(min_gb, 2),
            can_shrink_1gb=can_shrink,
            drive_m_available=data["DriveMAvailable"]
        )

    @classmethod
    def create_slice(cls, size_mb: int = 1024, dry_run: bool = False) -> Dict[str, Any]:
        """Reduz C: com segurança e cria a partição M: FAT32 para o Alpine."""
        if not cls.is_admin():
            raise PermissionError("Requer terminal como Administrador.")

        audit_data = cls.audit()
        if not audit_data.can_shrink_1gb:
            raise RuntimeError(
                f"Operação abortada por segurança: C: possui apenas {audit_data.free_space_gb:.2f} GB livres. "
                f"A margem de segurança exige pelo menos {cls.MIN_WINDOWS_FREE_MB} MB restantes para o Windows."
            )

        if not audit_data.drive_m_available:
            raise RuntimeError(f"A letra de unidade '{cls.TARGET_LETTER}:' já está em uso no sistema.")

        bytes_to_shrink = size_mb * 1024 * 1024
        ps_create = (
            f"$part = Get-Partition -DriveLetter C; "
            f"$newSize = $part.Size - {bytes_to_shrink}; "
            f"Resize-Partition -DriveLetter C -Size $newSize; "
            f"$newPart = New-Partition -DiskNumber $part.DiskNumber -Size {bytes_to_shrink} -DriveLetter {cls.TARGET_LETTER}; "
            f"Format-Volume -Partition $newPart -FileSystem FAT32 -NewFileSystemLabel '{cls.TARGET_LABEL}' -Confirm:$false | Out-Null; "
            f"'OK'"
        )

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "action": f"Reduzir C: em {size_mb} MB e criar {cls.TARGET_LETTER}: (FAT32, '{cls.TARGET_LABEL}')",
                "remaining_c_free_gb": round(audit_data.free_space_gb - (size_mb / 1024), 2)
            }

        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_create], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Erro na execução da partição: {res.stderr.strip()}")

        return {
            "success": True,
            "dry_run": False,
            "drive": f"{cls.TARGET_LETTER}:",
            "size_mb": size_mb,
            "label": cls.TARGET_LABEL
        }

    @classmethod
    def revert_slice(cls, dry_run: bool = False) -> Dict[str, Any]:
        """Remove a partição M: e expande C: de volta ao tamanho máximo."""
        if not cls.is_admin():
            raise PermissionError("Requer terminal como Administrador.")

        ps_revert = (
            f"Remove-Partition -DriveLetter {cls.TARGET_LETTER} -Confirm:$false; "
            f"$max = (Get-PartitionSupportedSize -DriveLetter C).SizeMax; "
            f"Resize-Partition -DriveLetter C -Size $max; "
            f"'OK'"
        )

        if dry_run:
            return {"success": True, "dry_run": True, "action": f"Remover {cls.TARGET_LETTER}: e expandir C: ao máximo"}

        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_revert], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Erro ao reverter partição: {res.stderr.strip()}")

        return {"success": True, "dry_run": False, "message": f"Partição {cls.TARGET_LETTER}: removida e C: expandido com sucesso."}

