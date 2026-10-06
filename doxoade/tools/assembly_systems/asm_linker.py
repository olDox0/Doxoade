# -*- coding: utf-8 -*-
"""
[JANUS] Assembly Linker v2.1
Linka objetos (.o) em binários finais. Integra com Janus para achar GCC.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class LinkResult:
    success: bool
    output: str
    command: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    size_bytes: int = 0


class AssemblyLinker:
    """Linker especializado para OS Dev e bare-metal."""

    KERNEL_FLAGS = [
        "-ffreestanding",
        "-nostdlib",
        "-nostdinc",
        "-fno-builtin",
        "-fno-stack-protector",
        "-fno-pie",
        "-no-pie",
    ]

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.linker_path = self._find_linker()

    def _find_linker(self) -> str:
        """Encontra o GCC/Linker ideal. Prioriza Janus e cross-compilers."""
        # 1) Prioridade: cross-compilers i686-elf (OS Dev)
        for name in ["i686-elf-gcc", "i686-elf-ld", "x86_64-elf-gcc", "x86_64-elf-ld"]:
            path = shutil.which(name)
            if path:
                self._ensure_in_path(path)
                return path

        # 2) Janus (cache ou detecção nova)
        try:
            from doxoade.tools.janus_systems.janus_manifest import JanusManifest
            from doxoade.tools.janus_systems.janus_detector import JanusDetector

            manifest = JanusManifest(self.root)
            cached = manifest.get_cached()
            if cached and os.path.exists(cached.compiler_path):
                self._ensure_in_path(cached.compiler_path)
                return cached.compiler_path

            detector = JanusDetector()
            info = detector.detect(project_root=self.root)
            if info:
                manifest.save(info)
                self._ensure_in_path(info.compiler_path)
                return info.compiler_path
        except Exception:
            pass

        # 3) PATH do sistema
        for name in ["gcc", "cc", "clang", "ld"]:
            path = shutil.which(name)
            if path:
                return path

        # 4) Caminhos canônicos do Windows
        if os.name == 'nt':
            candidates = [
                Path(r"C:\winlibs\mingw64\bin\gcc.exe"),
                Path(r"C:\winlibs-x86_64\mingw64\bin\gcc.exe"),
                Path(r"C:\msys64\mingw64\bin\gcc.exe"),
                Path(r"C:\msys64\ucrt64\bin\gcc.exe"),
                Path(r"C:\MinGW\bin\gcc.exe"),
                Path(r"C:\mingw64\bin\gcc.exe"),
            ]
            for c in candidates:
                if c.exists():
                    self._ensure_in_path(str(c))
                    return str(c)
            for base in Path("C:/").glob("winlibs*"):
                gcc = base / "mingw64" / "bin" / "gcc.exe"
                if gcc.exists():
                    self._ensure_in_path(str(gcc))
                    return str(gcc)

        # 5) Último recurso
        return "gcc"

    def _ensure_in_path(self, compiler_path: str) -> None:
        """Garante que o diretório do compilador esteja no PATH do processo."""
        c_dir = str(Path(compiler_path).parent)
        current_path = os.environ.get("PATH", "")
        if c_dir.lower() not in current_path.lower():
            os.environ["PATH"] = c_dir + os.pathsep + current_path

    def link(self, objects: List[str], output: str,
            linker_script: Optional[str] = None,
            extra_flags: Optional[List[str]] = None,
            kernel_mode: bool = True) -> LinkResult:
        """Linka objetos em binário final."""
        cmd = [self.linker_path]

        # ADICIONE ESTA LINHA:
        cmd.append("-m32")

        if kernel_mode:
            cmd.extend(self.KERNEL_FLAGS)

        if linker_script:
            ls_path = Path(linker_script)
            if not ls_path.is_absolute():
                ls_path = self.root / ls_path
            cmd.extend(["-T", str(ls_path)])

        cmd.extend(objects)
        cmd.extend(["-o", output])

        if extra_flags:
            cmd = cmd[:-2] + extra_flags + cmd[-2:]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.root),
                encoding="utf-8",
                errors="ignore",
            )
            success = proc.returncode == 0
            size = 0
            out_path = self.root / output
            if success and out_path.exists():
                size = out_path.stat().st_size

            return LinkResult(
                success=success,
                output=output,
                command=cmd,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                size_bytes=size,
            )
        except subprocess.TimeoutExpired:
            return LinkResult(False, output, cmd, stderr="Timeout (>120s)")
        except Exception as e:
            return LinkResult(False, output, cmd, stderr=str(e))
