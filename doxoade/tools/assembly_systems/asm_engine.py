# -*- coding: utf-8 -*-
"""
[ATENA] Assembly Engine v2.0 — Orquestrador.
Separa Flat Binaries (bootloader) de Kernel Objects (ELF32).
"""
import os
import glob
import subprocess
import shutil  # topo do arquivo
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

    def _convert_pe_to_elf(self, pe_obj: str) -> bool:
        """[ALQUIMIA] Converte objeto PE-i386 (MinGW) para ELF32-i386 via objcopy."""
        import click
        from doxoade.tools.doxcolors import Fore, Style
        
        linker_dir = Path(self.linker.linker_path).parent
        objcopy = linker_dir / "objcopy.exe"
        if not objcopy.exists():
            objcopy = linker_dir / "objcopy"
            
        if not objcopy.exists():
            click.echo(f"  {Fore.RED}✘ objcopy não encontrado em {linker_dir}{Style.RESET_ALL}")
            return False

        elf_obj = pe_obj + ".elf"
        cmd = [str(objcopy), "-I", "pe-i386", "-O", "elf32-i386", pe_obj, elf_obj]
        
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                os.replace(elf_obj, pe_obj)  # Substitui o PE pelo ELF
                return True
            else:
                click.echo(f"  {Fore.RED}✘ objcopy falhou: {proc.stderr}{Style.RESET_ALL}")
                return False
        except Exception as e:
            click.echo(f"  {Fore.RED}✘ Erro na conversão PE->ELF: {e}{Style.RESET_ALL}")
            return False

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
        # FASE 3: C → ELF32 (Zig soberano; fallback GCC + alquimia)
        # ═══════════════════════════════════════════
        zig = self._find_zig()
        ZIG_FLAGS = [
            "-target", "x86-freestanding-none",
            "-ffreestanding", "-fno-stack-protector", "-fno-sanitize=undefined",
            "-nostdlib", "-nostdinc", "-fno-builtin",
        ]
        for c_file in sources["c"]:
            obj = str(Path(c_file).with_suffix(".o"))
            if zig:
                cmd = [zig, "cc", *ZIG_FLAGS]
                cmd += [f"-I{d}" for d in include_dirs]
                cmd += ["-c", c_file, "-o", obj]
            else:
                cmd = [self.linker.linker_path, "-m32", "-ffreestanding",
                       "-nostdlib", "-nostdinc", "-fno-builtin",
                       "-fno-stack-protector", "-fno-pie", "-no-pie",
                       "-c", c_file, "-o", obj]
                cmd += [f"-I{d}" for d in include_dirs]

            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  cwd=str(self.root), timeout=60,
                                  encoding="utf-8", errors="ignore")
            if proc.returncode != 0:
                results["compile"].append(BuildResult(
                    False, c_file, obj, cmd,
                    proc.stdout, proc.stderr, proc.returncode))
                return results

            if not zig and not self._convert_pe_to_elf(obj):
                return results

            objects.append(obj)

        # ═══════════════════════════════════════════
        # FASE 4: Link ELF32 (LLD do Zig; fallback GCC)
        # ═══════════════════════════════════════════
        cfg = self.config.get("build", {})
        out_name = cfg.get("output", "kernel.bin")
        if zig:
            ls = self.root / cfg.get("linker_script", "linker.ld")
            cmd = [zig, "cc", "-target", "x86-freestanding-none", "-nostdlib",
                   "-ffreestanding", "-fno-sanitize=undefined",
                   "-T", str(ls), *objects, "-o", out_name]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  cwd=str(self.root), timeout=120,
                                  encoding="utf-8", errors="ignore")
            size = (self.root / out_name).stat().st_size if (self.root / out_name).exists() else 0
            link_res = LinkResult(proc.returncode == 0, out_name, cmd,
                                  proc.stdout, proc.stderr, proc.returncode, size)
        else:
            link_res = self.linker.link(objects, out_name,
                                        cfg.get("linker_script"),
                                        kernel_mode=cfg.get("kernel_mode", True))
        results["link"] = link_res
        results["success"] = link_res.success
        return results

    def _find_zig(self):
        import shutil
        zig = shutil.which("zig")
        if zig:
            return zig
        if os.name == "nt":
            local = Path(os.environ.get("LOCALAPPDATA", ""))
            link = local / "Microsoft" / "WinGet" / "Links" / "zig.exe"
            if link.exists():
                return str(link)
            hits = sorted(local.glob("Microsoft/WinGet/Packages/zig.zig_*/zig-*/zig.exe"))
            if hits:
                return str(hits[-1])
        return None

    def extract_flat(self, out="kernel_flat.bin") -> bool:
        """ELF -> flat binary via `zig objcopy` (fallback: objcopy Winlibs)."""
        kernel_bin = self.config.get("build", {}).get("output", "kernel.bin")
        zig = self._find_zig()
        cmd = [zig, "objcopy", "-O", "binary", kernel_bin, out] if zig else \
              [str(Path(self.linker.linker_path).parent / "objcopy.exe"),
               "-O", "binary", kernel_bin, out]
        return subprocess.run(cmd, capture_output=True, cwd=str(self.root)).returncode == 0

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
