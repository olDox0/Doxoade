# -*- coding: utf-8 -*-
# doxoade/tools/janus_systems/janus_bridge.py
"""
🏛️ JANUS BRIDGE — Ponte do Sistema de Compilação.
Responsável pela injeção no os.environ e montagem de comandos para GCC e Clang.
"""
from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path
from typing import List, Optional

from .janus_cpu import JanusCPU
from .janus_detector import CompilerInfo


class JanusBridge:
    """Ponte de execução entre o Python e o compilador C nativo."""

    def __init__(self, info: CompilerInfo):
        self.info = info

    def ensure_in_path(self):
        """Garante que a pasta 'bin' do compilador esteja no PATH do processo atual."""
        c_dir = str(Path(self.info.compiler_path).parent)
        current_path = os.environ.get("PATH", "")
        if c_dir.lower() not in current_path.lower():
            os.environ["PATH"] = c_dir + os.pathsep + current_path

        # Define variáveis canônicas de build
        os.environ["CC"] = self.info.compiler_path
        if self.info.gpp_path:
            os.environ["CXX"] = self.info.gpp_path

    def build_compile_command(
        self,
        sources: List[str | Path],
        output: str | Path,
        is_shared: bool = True,
        opt: str = "O2",
        include_python: bool = True,
        extra_flags: Optional[List[str]] = None
    ) -> List[str]:
        compiler = self.info.compiler_path
        cmd = [compiler]

        # 🛑 Injeta as flags exatas da CPU da máquina atual
        cpu_profile = JanusCPU.profile()
        cmd.extend(cpu_profile.optimal_cflags)

        cmd.append("-std=c11")

        if is_shared:
            cmd.append("-shared")
            if os.name != 'nt':
                cmd.append("-fPIC")

        if include_python:
            py_inc = sysconfig.get_path("include")
            if py_inc:
                cmd.append(f"-I{py_inc}")

        cmd.extend([str(s) for s in sources])
        cmd.extend(["-o", str(output)])

        if os.name == 'nt' and include_python:
            cmd.append("-static-libgcc")
            py_ver = f"{sys.version_info.major}{sys.version_info.minor}"
            py_lib_dir = Path(sys.base_prefix) / "libs"
            cmd.append(f"-L{py_lib_dir}")
            cmd.append(f"-lpython{py_ver}")

        if extra_flags:
            cmd.extend(extra_flags)

        return cmd
