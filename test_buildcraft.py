# -*- coding: utf-8 -*-
import os, sys, subprocess
from pathlib import Path

# Sincroniza path local
sys.path.insert(0, str(Path(__file__).resolve().parent))

from doxoade.tools.vulcan.buildcraft.dedalo_engine import DedaloEngine
from doxoade.tools.vulcan.diagnostic.soteria.soteria_analysis import SoteriaForensic

def main():
    print("🚀 [BUILD-CRAFT] Iniciando teste do DedaloEngine...")
    
    # Root do projeto
    bc = DedaloEngine(".")
    
    # Alvo de teste
    target = "double_free_test.c" 
    
    # Forja automatizada
    success, exe_path = bc.forge(target, use_soteria=True)
    
    if success:
        print(f"📡 [TESTE] Executando binário e canalizando para Sotéria...")
        proc = subprocess.run([exe_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        forensic = SoteriaForensic()
        if not forensic.process_pipe(proc.stdout + proc.stderr):
            print("⚠️ Falha ao resgatar evidências.")

if __name__ == "__main__":
    main()