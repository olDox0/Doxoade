# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/qemu_detector.py
"""
[ANÚBIS] QEMU & Firmware Radar v1.0.
Diagnóstico forense, detecção de aceleradores (KVM/WHPX) e localização de ROMs OVMF.
Compatível com arquiteturas x86 (IA-32) e x86_64 sob diretrizes do ProDeNov.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class QemuInfo:
    """Metadados de auditoria do emulador detectado."""
    arch: str
    path: str
    version: str
    accel: str           # 'kvm', 'whpx', 'tcg'
    is_operational: bool
    raw_probe: str = ""

    def __str__(self) -> str:
        accel_tag = f"[{self.accel.upper()}]" if self.accel else "[NO-ACCEL]"
        return f"QEMU-{self.arch} v{self.version} {accel_tag} @ {self.path}"


@dataclass
class OvmfInfo:
    """Metadados de imagens de firmware UEFI (OVMF)."""
    arch: str            # 'ia32' ou 'x64'
    path: Path
    description: str


class QemuDetector:
    """
    Radar de infraestrutura de emulação para OS-Dev.
    Implementa estratégia com Plano A (PATH e padrão) e Plano B (varredura profunda).
    """

    SUPPORTED_ARCHS = ["i386", "x86_64"]
    VERSION_REGEX = re.compile(r"version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

    # Caminhos canônicos no Windows (Plano B)
    WINDOWS_SEARCH_DIRS = [
        Path(r"C:\Program Files\qemu"),
        Path(r"C:\Program Files (x86)\qemu"),
        Path(r"C:\qemu"),
        Path(r"C:\msys64\mingw64\bin"),
        Path(r"C:\msys64\ucrt64\bin"),
    ]

    # Diretórios onde imagens OVMF costumam residir
    OVMF_SEARCH_DIRS_LINUX = [
        Path("/usr/share/OVMF"),
        Path("/usr/share/ovmf"),
        Path("/usr/share/edk2/ovmf"),
        Path("/usr/share/qemu"),
    ]

    @classmethod
    def detect(cls, arch: str = "i386") -> Optional[QemuInfo]:
        """
        Localiza o executável QEMU para uma arquitetura específica.
        Fluxo: Plano A (shutil.which) -> Plano B (varredura profunda de disco).
        """
        bin_name = f"qemu-system-{arch}"

        # -------------------------------------------------------------
        # PLANO A: Verificação direta via PATH do sistema
        # -------------------------------------------------------------
        resolved_path = shutil.which(bin_name)
        if resolved_path:
            probe = cls._probe_binary(resolved_path, arch)
            if probe:
                return probe

        # -------------------------------------------------------------
        # PLANO B: Varredura de diretórios canônicos e AppData (Windows)
        # -------------------------------------------------------------
        if os.name == "nt":
            candidates = cls._get_windows_candidates(bin_name)
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    probe = cls._probe_binary(str(candidate), arch)
                    if probe:
                        return probe

        return None

    @classmethod
    def detect_all(cls) -> Dict[str, Optional[QemuInfo]]:
        """Executa a detecção em todas as arquiteturas suportadas."""
        return {arch: cls.detect(arch) for arch in cls.SUPPORTED_ARCHS}

    @classmethod
    def _get_windows_candidates(cls, bin_name: str) -> List[Path]:
        """Gera lista de caminhos prováveis no Windows, incluindo Winget e AppData."""
        candidates = []
        exe_name = f"{bin_name}.exe"

        # Diretórios estáticos
        for base in cls.WINDOWS_SEARCH_DIRS:
            candidates.append(base / exe_name)

        # Winget e LocalAppData
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            base_app = Path(local_app)
            candidates.append(base_app / "Microsoft" / "WinGet" / "Links" / exe_name)
            # Glob nos pacotes Winget caso instalado via gerenciador de pacotes
            candidates.extend(list(base_app.glob(f"Microsoft/WinGet/Packages/*QEMU*/{exe_name}")))

        return candidates

    @classmethod
    def _probe_binary(cls, path_str: str, arch: str) -> Optional[QemuInfo]:
        """Executa `--version` e avalia se o binário está operacional."""
        try:
            res = subprocess.run(
                [path_str, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="ignore"
            )
            raw = res.stdout or res.stderr or ""
            match = cls.VERSION_REGEX.search(raw)
            version = match.group(1) if match else "desconhecida"

            accel = cls.detect_accel(path_str)

            return QemuInfo(
                arch=arch,
                path=os.path.abspath(path_str),
                version=version,
                accel=accel,
                is_operational=(res.returncode == 0),
                raw_probe=raw.splitlines()[0] if raw else ""
            )
        except Exception:
            return None

    @classmethod
    def detect_accel(cls, bin_path: str) -> str:
        """
        Diagnostica aceleração de hardware disponível.
        Retorna: 'kvm' (Linux), 'whpx' (Windows), ou 'tcg' (software fallback).
        """
        # Verificação nativa Linux
        if os.name == "posix" and os.path.exists("/dev/kvm"):
            if os.access("/dev/kvm", os.R_OK | os.W_OK):
                return "kvm"

        # Verificação nativa Windows via probe de aceleração do QEMU
        if os.name == "nt":
            try:
                probe = subprocess.run(
                    [bin_path, "-accel", "help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding="utf-8",
                    errors="ignore"
                )
                output = (probe.stdout + probe.stderr).lower()
                if "whpx" in output:
                    return "whpx"
                if "hax" in output or "haxm" in output:
                    return "haxm"
            except Exception:
                pass

        return "tcg"  # Tiny Code Generator (Emulação pura em software)

    @classmethod
    def find_ovmf(cls, arch: str = "ia32") -> Optional[OvmfInfo]:
        """
        Localiza imagens de ROM UEFI (OVMF).
        Suporta 'ia32' (para alvos Bay Trail) e 'x64'.
        """
        target_files = {
            "ia32": ["OVMF32.fd", "OVMF_IA32.fd", "OVMF-ia32.fd", "ovmf-ia32.bin"],
            "x64":  ["OVMF.fd", "OVMF_CODE.fd", "OVMF_X64.fd", "ovmf-x86_64.bin"]
        }

        names = target_files.get(arch, target_files["x64"])
        search_dirs: List[Path] = []

        if os.name == "posix":
            search_dirs.extend(cls.OVMF_SEARCH_DIRS_LINUX)
        elif os.name == "nt":
            for base in cls.WINDOWS_SEARCH_DIRS:
                search_dirs.append(base / "share")
                search_dirs.append(base)

        # Busca em pasta local 'firmware/' ou '.doxoade/firmware/' se existir
        search_dirs.append(Path("firmware"))
        search_dirs.append(Path(".doxoade") / "firmware")

        for directory in search_dirs:
            if not directory.exists():
                continue
            for name in names:
                candidate = directory / name
                if candidate.exists() and candidate.is_file():
                    return OvmfInfo(
                        arch=arch,
                        path=candidate.resolve(),
                        description=f"Firmware UEFI {arch.upper()} em {candidate.name}"
                    )

        return None

    @classmethod
    def audit_w5h2(cls) -> Dict[str, Any]:
        """
        Diagnóstico Forense W5+2H conforme exigido pelo ProDeNov (Art. 3.1.4).
        """
        i386_info = cls.detect("i386")
        x64_info = cls.detect("x86_64")
        ovmf_ia32 = cls.find_ovmf("ia32")
        ovmf_x64 = cls.find_ovmf("x64")

        return {
            "onde": "Host local (Ambiente de Execução e Emulação)",
            "o_que": "Infraestrutura de Emulação bare-metal e Firmwares",
            "quem": "Módulo QemuDetector (Doxoade Anúbis)",
            "quando": "Diagnóstico sob demanda em tempo de execução",
            "quanto": {
                "emuladores_ativos": sum(1 for e in [i386_info, x64_info] if e),
                "firmwares_encontrados": sum(1 for f in [ovmf_ia32, ovmf_x64] if f),
            },
            "por_que": "Garantir viabilidade de testes sem pendrive e isolar o hardware real",
            "origem": "Detecção de binários no sistema de arquivos",
            "consequencias": "Permite execução de testes automatizados com telemetria direta",
            "detalhes": {
                "i386": i386_info,
                "x86_64": x64_info,
                "ovmf_ia32": ovmf_ia32,
                "ovmf_x64": ovmf_x64,
            }
        }
