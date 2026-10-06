# -*- coding: utf-8 -*-
"""
[HEFESTO] Assembly Detector v2.1 (AppData & Polymorphic Radar).
"""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

@dataclass
class AssemblerInfo:
    name: str
    path: str
    version: str
    raw_output: str

    def __str__(self) -> str:
        return f"{self.name.upper()} {self.version} @ {self.path}"

class AssemblyDetector:
    VERSION_PATTERNS = {
        "nasm": re.compile(r"NASM\s+version\s+([\d\.]+)", re.IGNORECASE),
        "gas":  re.compile(r"GNU\s+assembler\s+(?:\([^)]+\)\s+)?([\d\.]+)", re.IGNORECASE),
    }

    @classmethod
    def detect_all(cls) -> dict:
        return {"nasm": cls.detect("nasm"), "gas": cls.detect("gas")}

    @classmethod
    def detect(cls, asm_type: str) -> Optional[AssemblerInfo]:
        bin_name = "nasm" if asm_type == "nasm" else "as"
        
        # 1. Tenta o PATH do sistema
        path = shutil.which(bin_name)
        if path:
            info = cls._probe(path, asm_type)
            if info: return info

        # 2. Varredura de caminhos canônicos no Windows
        if os.name == 'nt':
            for c in cls._get_windows_candidates(asm_type):
                if c.exists():
                    info = cls._probe(str(c), asm_type)
                    if info: return info
                    
        return None

    @classmethod
    def _get_windows_candidates(cls, asm_type: str) -> List[Path]:
        candidates = []
        if asm_type == "nasm":
            # AppData (Winget padrão)
            appdata = os.environ.get("LOCALAPPDATA", "")
            if appdata:
                candidates.append(Path(appdata) / "bin" / "NASM" / "nasm.exe")
                candidates.append(Path(appdata) / "Microsoft" / "WinGet" / "Packages" / "NASM.NASM_Microsoft.Winget.Source_8wekyb3d8bbwe" / "nasm.exe")
            
            # Caminhos manuais e glob
            candidates.extend([
                Path(r"C:\Program Files\NASM\nasm.exe"),
                Path(r"C:\Program Files (x86)\NASM\nasm.exe"),
                Path(r"C:\nasm\nasm.exe"),
            ])
            # Glob para C:\nasm-* (caso o zip tenha extraído com versão)
            for p in Path("C:/").glob("nasm*/nasm.exe"):
                candidates.append(p)
                
        elif asm_type == "gas":
            candidates.extend([
                Path(r"C:\winlibs\mingw64\bin\as.exe"),
                Path(r"C:\msys64\mingw64\bin\as.exe"),
            ])
            for base in Path("C:/").glob("winlibs*"):
                candidates.append(base / "mingw64" / "bin" / "as.exe")
        return candidates

    @classmethod
    def _probe(cls, path: str, asm_type: str) -> Optional[AssemblerInfo]:
        try:
            proc = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="ignore"
            )
            raw = (proc.stdout or "") + (proc.stderr or "")
            pattern = cls.VERSION_PATTERNS.get(asm_type)
            match = pattern.search(raw) if pattern else None
            version = match.group(1) if match else "unknown"
            
            return AssemblerInfo(
                name=asm_type,
                path=os.path.abspath(path),
                version=version,
                raw_output=raw.strip()
            )
        except Exception:
            return None

    @classmethod
    def detect_for_extension(cls, ext: str) -> Optional[AssemblerInfo]:
        ext = ext.lower()
        if ext == ".asm": return cls.detect("nasm")
        elif ext == ".s": return cls.detect("gas")
        return None
