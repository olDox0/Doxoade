# -*- coding: utf-8 -*-
"""
[ATENA] Assembly Engine v2.0 — Orquestrador.
Separa Flat Binaries (bootloader) de Kernel Objects (ELF32).
"""
import os
import glob
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from .asm_builder import AssemblyBuilder, BuildResult
from .asm_linker import AssemblyLinker, LinkResult


class AssemblyEngine:
    """Orquestrador de builds Assembly+C para OS Dev."""

    CONFIG_FILES = ("laurix.toml", "assembly.toml", "doxoade_asm.toml")

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.builder = AssemblyBuilder(str(self.root))
        self.linker = AssemblyLinker(str(self.root))
        self.config = self._load_config()

    def _load_config(self) -> dict:
        for fname in self.CONFIG_FILES:
            cfg_path = self.root / fname
            if cfg_path.exists() and tomllib:
                try:
                    with open(cfg_path, "rb") as f:
                        return tomllib.load(f)
                except Exception:
                    pass
        return self._default_config()

    def _default_config(self) -> dict:
        return {
            "project": {"name": "laurix", "arch": "x86"},
            "build": {
                "sources": [
                    "core/kernel_entry.asm",
                    "include/*.asm",
                    "include/*.c",
                    "kernel.c"
                ],
                "flat_binaries": ["core/bootloader.asm"],
                "include_dirs": ["include"],
                "linker_script": "linker.ld",
                "output": "kernel.bin",
                "kernel_mode": True,
            },
        }

    def discover_sources(self) -> dict:
        """Descobre fontes separando kernel (ELF) de flat binaries (BIN)."""
        cfg = self.config.get("build", {})
        kernel_patterns = cfg.get("sources", [])
        flat_patterns = cfg.get("flat_binaries", [])

        asm_files, c_files, bin_files = [], [], []

        # Descobre fontes do kernel (ELF32)
        for pattern in kernel_patterns:
            for f in glob.glob(str(self.root / pattern), recursive=True):
                rel = os.path.relpath(f, self.root).replace("\\", "/")
                if rel.endswith((".asm", ".s")):
                    asm_files.append(rel)
                elif rel.endswith(".c"):
                    c_files.append(rel)

        # Descobre flat binaries (bootloader)
        for pattern in flat_patterns:
            for f in glob.glob(str(self.root / pattern), recursive=True):
                rel = os.path.relpath(f, self.root).replace("\\", "/")
                bin_files.append(rel)

        return {
            "asm": sorted(set(asm_files)),
            "c": sorted(set(c_files)),
            "bin": sorted(set(bin_files)),
        }

    def build(self, clean: bool = False) -> dict:
        """Executa o build completo: bootloader (bin) + kernel (elf32) + link."""
        results = {"compile": [], "link": None, "success": False}

        if clean:
            self.clean()

        sources = self.discover_sources()
        include_dirs = self.config.get("build", {}).get("include_dirs", [])
        abs_includes = [str(self.root / d) for d in include_dirs]
        objects = []

        # ═══════════════════════════════════════════
        # FASE 1: Compila Flat Binaries (Bootloader)
        # ═══════════════════════════════════════════
        for bin_src in sources["bin"]:
            out_bin = str(Path(bin_src).with_suffix(".bin"))
            res = self.builder.compile(
                bin_src,
                output=out_bin,
                include_dirs=abs_includes,
                fmt="bin",  # <-- FLAT BINARY
            )
            results["compile"].append(res)
            if not res.success:
                return results
            # Não adiciona ao objects[] — bootloader não é linkado

        # ═══════════════════════════════════════════
        # FASE 2: Compila Assembly do Kernel (ELF32)
        # ═══════════════════════════════════════════
        for asm in sources["asm"]:
            res = self.builder.compile(
                asm,
                include_dirs=abs_includes,
                fmt="elf32",  # <-- ELF32 para linkar
            )
            results["compile"].append(res)
            if res.success:
                objects.append(res.output)
            else:
                return results

        # ═══════════════════════════════════════════
        # FASE 3: Compila C do Kernel (ELF32)
        # ═══════════════════════════════════════════
        # Usa o linker_path que agora deve ser o cross-compiler i686-elf-gcc
        c_compiler = self.linker.linker_path

        for c_file in sources["c"]:
            obj = str(Path(c_file).with_suffix(".o"))
            cmd = [
                c_compiler,
                "-ffreestanding", "-nostdlib",
                "-nostdinc", "-fno-builtin", "-fno-stack-protector",
                "-fno-pie", "-no-pie",
                "-m32",  # Mantém -m32 por segurança
                "-c", c_file, "-o", obj,
            ]
            for d in include_dirs:
                cmd.insert(-3, f"-I{d}")

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.root),
                timeout=60,
                encoding="utf-8",
                errors="ignore",
            )
            if proc.returncode == 0:
                objects.append(obj)
            else:
                results["compile"].append(BuildResult(
                    False, c_file, obj, cmd,
                    proc.stdout, proc.stderr, proc.returncode
                ))
                return results

        # ═══════════════════════════════════════════
        # FASE 4: Linka apenas os objetos ELF32
        # ═══════════════════════════════════════════
        cfg = self.config.get("build", {})
        link_res = self.linker.link(
            objects=objects,
            output=cfg.get("output", "kernel.bin"),
            linker_script=cfg.get("linker_script"),
            kernel_mode=cfg.get("kernel_mode", True),
        )
        results["link"] = link_res
        results["success"] = link_res.success
        return results

    def clean(self) -> int:
        """Remove todos os .o, .bin e artefatos."""
        removed = 0
        for ext in ("*.o", "*.bin", "*.elf"):
            for f in self.root.rglob(ext):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
        return removed

    def status(self) -> dict:
        from .asm_detector import AssemblyDetector
        self.builder.manifest.refresh(force=True)
        return {
            "assemblers": AssemblyDetector.detect_all(),
            "linker": self.linker.linker_path,
            "config": self.config,
            "sources": self.discover_sources(),
        }
