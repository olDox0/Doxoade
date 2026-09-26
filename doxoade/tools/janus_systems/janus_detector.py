# -*- coding: utf-8 -*-
# doxoade/tools/janus_systems/janus_detector.py
"""
🏛️ JANUS DETECTOR — Scanner Polimórfico de Compiladores C/C++.
Descobre automaticamente compiladores no Android (Termux Clang),
Windows (MinGW, WinLibs, MSYS2, LLVM) e Linux (GCC/Clang).
"""
from __future__ import annotations

import os
import sys
import shutil
import platform
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List


@dataclass
class CompilerInfo:
    """Informações e capacidades do compilador C detectado."""
    compiler_path: str
    gpp_path: Optional[str]
    compiler_type: str  # 'gcc', 'clang', 'unknown'
    version: str
    target_machine: str  # x86_64, aarch64, etc.
    is_clang: bool
    supports_simd: bool
    provider: str  # 'termux', 'winlibs', 'mingw', 'system_path', 'w64devkit_legacy'


class JanusDetector:
    """Especialista em varredura e inferência de capacidades de compiladores."""

    @staticmethod
    def is_termux() -> bool:
        return bool(os.environ.get("TERMUX_VERSION") or os.path.exists("/data/data/com.termux"))

    def detect(self, project_root: Optional[Path] = None) -> Optional[CompilerInfo]:
        """Executa a varredura ordenada por prioridade da plataforma."""
        # 1. Se estiver no Termux (Android / Cantaloupe), busca prioritariamente o Clang
        if self.is_termux():
            info = self._detect_termux()
            if info:
                return info

        # 2. Se estiver no Windows (Amaranth / Bluebaby), busca MinGW / WinLibs / MSYS2
        if os.name == 'nt':
            info = self._detect_windows(project_root)
            if info:
                return info

        # 3. Linux / macOS / WSL
        return self._detect_posix()

    def _detect_termux(self) -> Optional[CompilerInfo]:
        """Procura Clang nativo do Termux."""
        candidates = [
            Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "bin" / "clang",
            Path("/data/data/com.termux/files/usr/bin/clang"),
        ]
        which_clang = shutil.which("clang")
        if which_clang:
            candidates.insert(0, Path(which_clang))

        for c in candidates:
            if c.exists() and os.access(c, os.X_OK):
                gpp = c.parent / "clang++"
                return self._probe_compiler(str(c), str(gpp) if gpp.exists() else None, provider="termux")

        return None

    def _detect_windows(self, project_root: Optional[Path]) -> Optional[CompilerInfo]:
        """Varre WinLibs, MinGW, MSYS2 e PATH do Windows."""
        # 1. Checa PATH primeiro
        gcc_in_path = shutil.which("gcc")
        if gcc_in_path:
            gpp = shutil.which("g++") or str(Path(gcc_in_path).parent / "g++.exe")
            return self._probe_compiler(gcc_in_path, gpp if Path(gpp).exists() else None, provider="system_path")

        clang_in_path = shutil.which("clang")
        if clang_in_path:
            gpp = shutil.which("clang++") or str(Path(clang_in_path).parent / "clang++.exe")
            return self._probe_compiler(clang_in_path, gpp if Path(gpp).exists() else None, provider="system_path")

        # 2. Pastas canônicas do WinLibs (Bluebaby)
        winlibs_patterns = [
            Path("C:/winlibs"),
            Path("C:/winlibs-x86_64"),
            *Path("C:/").glob("winlibs*"),
        ]
        for base in winlibs_patterns:
            gcc = base / "bin" / "gcc.exe"
            if gcc.exists():
                gpp = base / "bin" / "g++.exe"
                return self._probe_compiler(str(gcc), str(gpp) if gpp.exists() else None, provider="winlibs")

        # 3. Pastas canônicas do MinGW (Amaranth)
        mingw_dirs = [
            Path("C:/MinGW"),
            Path("C:/mingw64"),
            Path("C:/mingw32"),
            Path("C:/msys64/ucrt64"),
            Path("C:/msys64/mingw64"),
        ]
        for base in mingw_dirs:
            gcc = base / "bin" / "gcc.exe"
            if gcc.exists():
                gpp = base / "bin" / "g++.exe"
                return self._probe_compiler(str(gcc), str(gpp) if gpp.exists() else None, provider="mingw")

        # 4. Fallback legado em thirdparty (se existir no projeto)
        if project_root:
            w64 = Path(project_root) / "thirdparty" / "w64devkit" / "bin" / "gcc.exe"
            if w64.exists():
                gpp = w64.parent / "g++.exe"
                return self._probe_compiler(str(w64), str(gpp) if gpp.exists() else None, provider="w64devkit_legacy")

        return None

    def _detect_posix(self) -> Optional[CompilerInfo]:
        """Varre GCC e Clang no Linux/macOS."""
        for name, provider in [("clang", "llvm"), ("gcc", "gnu")]:
            bin_path = shutil.which(name)
            if bin_path:
                gpp = shutil.which(f"{name}++")
                return self._probe_compiler(bin_path, gpp, provider=provider)
        return None

    def _probe_compiler(self, compiler_path: str, gpp_path: Optional[str], provider: str) -> Optional[CompilerInfo]:
        """Executa probe rápido para capturar versão e arquitetura."""
        try:
            res_v = subprocess.run([compiler_path, "--version"], capture_output=True, text=True, timeout=3)
            version_line = res_v.stdout.splitlines()[0] if res_v.stdout else "unknown"

            # Detecta se é Clang ou GCC
            is_clang = "clang" in version_line.lower()
            compiler_type = "clang" if is_clang else "gcc"

            # Detecta máquina/arquitetura
            res_m = subprocess.run([compiler_path, "-dumpmachine"], capture_output=True, text=True, timeout=2)
            machine = res_m.stdout.strip() if res_m.returncode == 0 else platform.machine()

            # Suporte básico a SIMD (x86_64 quase sempre suporta SSE)
            supports_simd = any(arch in machine.lower() for arch in ("x86_64", "amd64", "aarch64", "arm64"))

            return CompilerInfo(
                compiler_path=os.path.abspath(compiler_path),
                gpp_path=os.path.abspath(gpp_path) if gpp_path else None,
                compiler_type=compiler_type,
                version=version_line,
                target_machine=machine,
                is_clang=is_clang,
                supports_simd=supports_simd,
                provider=provider
            )
        except Exception:
            return None
