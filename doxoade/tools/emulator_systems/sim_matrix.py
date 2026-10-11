# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/sim_matrix.py
"""
[HÓRUS] Motor de Despacho Matricial Multi-Firmware.
Traduz perfis declarativos de hardware em execuções supervisionadas do QEMU.
Em total conformidade com o protocolo ProDeNov v2.0.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .sim_profiles import SimulationProfile, ProfileCatalog
from .qemu_detector import QemuDetector, OvmfInfo
from .qemu_runner import QemuRunner, QemuRunConfig, RunResult


class SimulationMatrix:
    """
    Orquestrador soberano de simulação multi-perfil.
    Garante a fidelidade de hardware entre BIOS clássica, Bay Trail IA-32 e UEFI x86_64.
    """

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.runner = QemuRunner(str(self.root))

    def run(
        self,
        profile_query: str,
        custom_image: Optional[str] = None,
        memory_mb: Optional[int] = None,
        dry_run: bool = False,
        extra_args: Optional[List[str]] = None
    ) -> RunResult:
        """
        [HÓRUS DISPATCH] Resolve o perfil e executa o emulador com calibração automática.
        """
        # 1. Resolução do Perfil no Catálogo
        profile = ProfileCatalog.resolve(profile_query)
        if not profile:
            valid_names = ", ".join(p.name for p in ProfileCatalog.list_all())
            return RunResult(
                success=False,
                return_code=-1,
                command=[],
                message=f"Perfil '{profile_query}' desconhecido. Perfis válidos: {valid_names}"
            )

        # 2. Resolução da Imagem de Disco
        image_name = custom_image or profile.default_image
        image_path = Path(image_name)
        if not image_path.is_absolute():
            image_path = self.root / image_path

        # Salvaguarda: Se a imagem não existir e não for dry-run, avisa antes de travar
        if not dry_run and not image_path.exists():
            forge_hint = (
                f"doxoade os-cmd forge {image_name} --arch x64"
                if profile.arch == "x86_64"
                else f"doxoade os-cmd forge {image_name} --arch ia32"
            )
            return RunResult(
                success=False,
                return_code=-1,
                command=[],
                message=(
                    f"Imagem de disco '{image_name}' não encontrada.\n"
                    f"  💡 Forje a mídia antes com: {forge_hint}"
                )
            )

        # 3. Resolução de Firmware (PFlash vs BIOS Legada)
        uefi_rom_path: Optional[Path] = None
        if profile.firmware_type == "pflash_ia32":
            ovmf_info: Optional[OvmfInfo] = QemuDetector.find_ovmf("ia32")
            if not ovmf_info:
                return RunResult(
                    success=False,
                    return_code=-1,
                    command=[],
                    message="ROM UEFI IA-32 (EDK2) não encontrada no sistema."
                )
            uefi_rom_path = ovmf_info.path

        elif profile.firmware_type == "pflash_x64":
            ovmf_info = QemuDetector.find_ovmf("x64")
            if not ovmf_info:
                return RunResult(
                    success=False,
                    return_code=-1,
                    command=[],
                    message="ROM UEFI x86_64 (EDK2) não encontrada no sistema."
                )
            uefi_rom_path = ovmf_info.path

        # 4. Construção das Flags de Máquina e Barramento
        # Chipset moderno Q35 ou i440FX clássico
        machine_flags: List[str] = ["-machine", profile.machine_type]
        if profile.extra_flags:
            machine_flags.extend(profile.extra_flags)
        if extra_args:
            machine_flags.extend(extra_args)

        # 5. Configuração do Supervisor
        ram_alloc = memory_mb or profile.default_ram_mb
        cfg = QemuRunConfig(
            image_path=str(image_path),
            arch=profile.arch,
            memory_mb=ram_alloc,
            media_type="drive",
            uefi_rom=uefi_rom_path,
            serial_mode="file",          # Blindagem: nunca quebra/limpa o terminal do host
            force_tcg=True,              # Determinismo de depuração
            dry_run=dry_run,
            extra_args=machine_flags
        )

        return self.runner.run(cfg)

    def audit_profiles(self) -> Dict[str, Any]:
        """Auditoria Ma'at dos perfis disponíveis e integridade de ROMs."""
        catalog = ProfileCatalog.list_all()
        status_report = []

        for p in catalog:
            rom_ok = True
            if p.firmware_type == "pflash_ia32":
                rom_ok = QemuDetector.find_ovmf("ia32") is not None
            elif p.firmware_type == "pflash_x64":
                rom_ok = QemuDetector.find_ovmf("x64") is not None

            img_path = self.root / p.default_image
            status_report.append({
                "perfil": p.name,
                "era": p.description.split("—")[0].strip(),
                "arch": p.arch,
                "chipset": p.machine_type,
                "ram_segura": f"{p.default_ram_mb} MB",
                "rom_pronta": rom_ok,
                "imagem_pronta": img_path.exists(),
            })

        return {"perfis": status_report}
