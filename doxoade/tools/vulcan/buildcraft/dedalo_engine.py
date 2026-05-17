# -*- coding: utf-8 -*-
# doxoade\tools\vulcan\buildcraft\dedalo_engine.py
import os, sys, subprocess, time
from pathlib import Path
from ..diagnostic.soteria.scribe import SoteriaScribe

class DedaloEngine:
    """
    Dedalo BuildCraft — O Orquestrador de Forja Nativa (Hefesto Domain).
    PASC 8.8: Fluxo explícito de construção e linkagem modular.
    """
    def __init__(self, project_root):
        self.root = Path(project_root).resolve()
        self.scribe = SoteriaScribe()
        self.foundry = self.root / "build" / "foundry"
        self.bin_out = self.root / "build" / "bin"
        
        # Localização da Sotéria no Doxoade
        self.soteria_dir = Path(__file__).resolve().parents[1] / "diagnostic" / "soteria"
        self.soteria_inc = self.soteria_dir / "include"
        self.soteria_src = self.soteria_dir / "src"

    def _setup_env(self):
        """Garante diretórios de metalurgia (PASC 3.3)."""
        self.foundry.mkdir(parents=True, exist_ok=True)
        self.bin_out.mkdir(parents=True, exist_ok=True)

    def forge(self, target_c_file, use_soteria=True):
        """Compila um arquivo C com o escudo Sotéria integrado."""
        self._setup_env()
        t_start = time.perf_counter()
        
        # Busca resiliente do alvo
        target_path = Path(target_c_file).resolve()
        if not target_path.exists():
            target_path = (self.root / target_c_file).resolve()
            
        if not target_path.exists():
            print(f"   🚨 [DÉDALO] Arquivo fonte não localizado: {target_c_file}")
            return False, None

        name = target_path.stem
        
        # 1. Vacinação (Hórus Scribe)
        shadow_c = self.foundry / f"{name}_vacinado.c"
        print(f"   💉 [DÉDALO] Injetando rastro em: {name}...")
        
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            vacinado = self.scribe.instrument_code(f.read(), target_path.name)
        with open(shadow_c, 'w', encoding='utf-8') as f:
            f.write(vacinado)

        # 2. Coleta de Módulos (PASC 8.13)
        sources = [str(shadow_c)]
        if use_soteria:
            sources.extend([str(m) for m in self.soteria_src.glob("*.c")])

        output_exe = self.bin_out / f"{name}.exe"

        # 3. Metalurgia (GCC)
        cmd = [
            "gcc", "-O0", "-g3",
            f'-I"{str(self.soteria_inc)}"',
            f'-I"{str(target_path.parent)}"'
        ] + [f'"{s}"' for s in sources] + [
            "-ldbghelp", "-lpsapi",
            "-o", f'"{str(output_exe)}"'
        ]

        try:
            # PASC 6.10: Normalização de barras para o Windows
            full_cmd = " ".join(cmd).replace("\\", "/")
            res = subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
            
            if res.returncode == 0:
                elapsed = time.perf_counter() - t_start
                print(f"   ✅ [DÉDALO] Forja concluída: {output_exe.name} ({elapsed:.2f}s)")
                return True, str(output_exe)
            else:
                print(f"   ❌ [DÉDALO] Erro de Metalurgia:\n{res.stderr}")
                return False, None
        except Exception as e:
            print(f"   🚨 [DÉDALO] Erro crítico na orquestração: {e}")
            return False, None