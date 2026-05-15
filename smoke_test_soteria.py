# -*- coding: utf-8 -*-
import os, sys, subprocess, shutil
from pathlib import Path
from types import SimpleNamespace

# PASC 9.1: Sincronia de ambiente local
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from doxoade.tools.vulcan.compiler import VulcanCompiler
from doxoade.tools.vulcan.diagnostic.soteria.engine import SoteriaForensic

def run_intensive_test():
    if sys.platform == 'win32': os.system('chcp 65001 > nul')
    
    print("🔥 [SOTÉRIA] Iniciando Prova de Fogo (Full-Stack Traceback)...")
    
    # 1. Setup de Pastas (PASC 8.20)
    test_dir = root / "build_soteria_test"
    if test_dir.exists(): shutil.rmtree(test_dir)
    foundry = test_dir / "foundry"
    bin_out = test_dir / "bin"
    foundry.mkdir(parents=True); bin_out.mkdir(parents=True)

    # 2. Configuração do Compilador
    # O root aponta para onde está o kamikaze.pyx
    mock_env = SimpleNamespace(root=str(root), foundry=foundry, bin_dir=bin_out)
    compiler = VulcanCompiler(mock_env)
    
    # 3. Metalurgia (Build)
    # use_soteria=True ativa o Shadow Build do .pyx
    if compiler.transpile_batch(["kamikaze"], use_soteria=True):
        if compiler._run_gcc_direct("kamikaze", use_soteria=True):
            print("🚀 [VULCAN] Módulo Kamikaze forjado e protegido.")
            
            # 4. Execução (O Crash)
            exec_code = f"import sys; sys.path.append(r'{bin_out}'); import kamikaze; kamikaze.provocar_falha()"
            cmd = [sys.executable, "-c", exec_code]
            
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            
            # 5. Resgate (Sotéria Engine)
            print("\n--- [INICIANDO RELATÓRIO SOTÉRIA] ---")
            forensic = SoteriaForensic()
            if not forensic.process_pipe(proc.stdout + proc.stderr):
                print("⚠️  Falha no resgate. Saída bruta:")
                print(proc.stdout); print(proc.stderr)
    else:
        print("❌ Falha na compilação.")

if __name__ == "__main__":
    run_intensive_test()