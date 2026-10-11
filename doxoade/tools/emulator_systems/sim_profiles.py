# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/sim_profiles.py
"""
[ANÚBIS/HEFESTO] Catálogo de Perfis de Hardware para Simulação Matricial.
Define as 3 eras computacionais: Bay Trail Q35 (IA-32), Legacy BIOS e Modern UEFI x64.
Alinhado com as restrições de memória do host sob o protocolo ProDeNov v2.0.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SimulationProfile:
    """Perfil declarativo de máquina e firmware para emulação no QEMU."""
    name: str
    aliases: List[str]
    description: str
    arch: str                    # 'i386' ou 'x86_64'
    machine_type: str            # 'q35' ou 'pc' (i440fx)
    default_ram_mb: int          # Calibrado para o host (128 MB a 256 MB)
    firmware_type: str           # 'pflash_ia32', 'pflash_x64', 'bios'
    default_image: str           # Imagem padrão de disco
    bus_type: str                # 'ahci' ou 'ide'
    extra_flags: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Catálogo Canônico das 3 Eras de Hardware
# --------------------------------------------------------------------------
_PROFILE_BAYTRAIL = SimulationProfile(
    name="baytrail",
    aliases=["n2808", "uefi32", "izanami", "positivo"],
    description="Positivo H14BT58 (2015) — Intel Celeron N2808, Chipset Q35, UEFI IA-32 EDK2",
    arch="i386",
    machine_type="q35",
    default_ram_mb=256,          # Seguro para os 154 MB livres do host Amaranth
    firmware_type="pflash_ia32",
    default_image="uefi_baytrail.img",
    bus_type="ahci",
    extra_flags=["-accel", "tcg"]
)

_PROFILE_LEGACY = SimulationProfile(
    name="legacy",
    aliases=["bios", "laurix", "mbr", "i440fx"],
    description="IBM-PC Clássico (1996) — Chipset i440FX, SeaBIOS Legada de 16 bits, IDE",
    arch="i386",
    machine_type="pc",
    default_ram_mb=128,
    firmware_type="bios",
    default_image="laurix.img",
    bus_type="ide",
    extra_flags=[]
)

_PROFILE_UEFI64 = SimulationProfile(
    name="uefi64",
    aliases=["x64", "modern", "x86_64"],
    description="PC / Servidor Moderno — Chipset Q35, UEFI x86_64 EDK2, AHCI SATA",
    arch="x86_64",
    machine_type="q35",
    default_ram_mb=256,
    firmware_type="pflash_x64",
    default_image="uefi_x64.img",
    bus_type="ahci",
    extra_flags=["-accel", "tcg"]
)


class ProfileCatalog:
    """Motor de descoberta e resolução de perfis de hardware."""

    _CATALOG: Dict[str, SimulationProfile] = {
        _PROFILE_BAYTRAIL.name: _PROFILE_BAYTRAIL,
        _PROFILE_LEGACY.name: _PROFILE_LEGACY,
        _PROFILE_UEFI64.name: _PROFILE_UEFI64,
    }

    @classmethod
    def resolve(cls, query: str) -> Optional[SimulationProfile]:
        """
        Localiza um perfil por nome canônico ou apelido (case-insensitive).
        Ex: 'baytrail', 'n2808', 'bios', 'laurix', 'uefi64', 'x64'.
        """
        key = query.strip().lower()

        # Busca direta por nome exato
        if key in cls._CATALOG:
            return cls._CATALOG[key]

        # Busca por aliases
        for profile in cls._CATALOG.values():
            if key in profile.aliases:
                return profile

        return None

    @classmethod
    def list_all(cls) -> List[SimulationProfile]:
        """Retorna todos os perfis canônicos suportados."""
        return list(cls._CATALOG.values())
