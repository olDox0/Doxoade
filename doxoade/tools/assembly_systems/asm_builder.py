# -*- coding: utf-8 -*-
"""
[VULCAN] Assembly Builder v2.0.
Compila .asm (NASM) e .s (GAS) em objetos (.o) ou flat binaries (.bin).
"""
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .asm_detector import AssemblerInfo
from .asm_manifest import AssemblyManifest


@dataclass
class BuildResult:
    success: bool
    source: str
    output: str
    command: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1


class AssemblyBuilder:
    """Compilador de Assembly multi-dialeto com suporte a flat binaries."""

    # Flags padrão por assembler e formato
    FORMAT_FLAGS = {
        "nasm": {
            "elf32": ["-f", "elf32"],
            "elf64": ["-f", "elf64"],
            "bin":   ["-f", "bin"],     # Flat binary para bootloaders
        },
        "gas": {
            "elf32": ["--32"],
            "elf64": ["--64"],
            "bin":   [],  # GAS não gera flat bin nativamente
        },
    }

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.manifest = AssemblyManifest(str(self.root))
        if not self.manifest.is_fresh():
            self.manifest.refresh()

    def compile(self, source: str, output: Optional[str] = None,
                extra_flags: Optional[List[str]] = None,
                include_dirs: Optional[List[str]] = None,
                fmt: str = "elf32") -> BuildResult:
        """Compila um arquivo fonte. fmt pode ser 'elf32', 'elf64' ou 'bin'."""
        src_path = Path(source)
        if not src_path.is_absolute():
            src_path = self.root / src_path

        if not src_path.exists():
            return BuildResult(False, str(source), output or "",
                               stderr=f"Arquivo não encontrado: {src_path}")

        # Escolhe assembler pela extensão
        asm_info = self.manifest.get_for_extension(src_path.suffix)
        if not asm_info:
            return BuildResult(
                False, str(source), output or "",
                stderr=f"Nenhum assembler encontrado para extensão {src_path.suffix}. "
                       f"Rode 'doxoade asm status' para diagnosticar."
            )

        # Valida formato
        if fmt not in self.FORMAT_FLAGS.get(asm_info.name, {}):
            return BuildResult(
                False, str(source), output or "",
                stderr=f"Formato '{fmt}' não suportado por {asm_info.name.upper()}."
            )

        # Define output padrão baseado no formato
        if not output:
            if fmt == "bin":
                output = str(src_path.with_suffix(".bin"))
            else:
                output = str(src_path.with_suffix(".o"))

        # Monta o comando
        cmd = self._build_command(asm_info, str(src_path), output,
                                  extra_flags, include_dirs, fmt)

        # Executa
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.root),
                encoding="utf-8",
                errors="ignore",
            )
            success = proc.returncode == 0
            return BuildResult(
                success=success,
                source=str(source),
                output=output,
                command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return BuildResult(False, str(source), output, cmd,
                               stderr="Timeout (>60s)")
        except Exception as e:
            return BuildResult(False, str(source), output, cmd,
                               stderr=str(e))

    def _build_command(self, asm_info: AssemblerInfo, source: str, output: str,
                       extra_flags: Optional[List[str]],
                       include_dirs: Optional[List[str]],
                       fmt: str) -> List[str]:
        cmd = [asm_info.path]

        # Adiciona flags de formato
        format_flags = self.FORMAT_FLAGS.get(asm_info.name, {}).get(fmt, [])
        cmd.extend(format_flags)

        # Adiciona include dirs
        if include_dirs:
            for d in include_dirs:
                cmd.extend(["-I", d])

        # Output e source
        cmd.extend(["-o", output, source])

        # Flags extras antes do output
        if extra_flags:
            cmd = cmd[:-2] + extra_flags + cmd[-2:]

        return cmd

    def compile_many(self, sources: List[str], **kwargs) -> List[BuildResult]:
        """Compila múltiplos arquivos."""
        return [self.compile(src, **kwargs) for src in sources]
