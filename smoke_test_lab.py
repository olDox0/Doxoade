# -*- coding: utf-8 -*-
import os, sys, subprocess
from pathlib import Path
from doxoade.tools.vulcan.buildcraft.dedalo_engine import DedaloEngine
from doxoade.tools.vulcan.diagnostic.soteria.soteria_analysis import SoteriaForensic

def testar_cenario(label, filename):
    print(f"\n🧪 [TESTE] Cenário: {label}")
    from doxoade.tools.vulcan.buildcraft.dedalo_engine import DedaloEngine
    from doxoade.tools.vulcan.diagnostic.soteria.soteria_analysis import SoteriaForensic
    
    bc = DedaloEngine(".")
    
    # 1. Forja o binário vacinado
    target_path = Path("doxoade/experiments/soteria_lab") / filename
    success, exe_path = bc.forge(str(target_path), use_soteria=True)
    
    if not success:
        print(f"   ❌ Falha na forja do arquivo {filename}")
        return

    # 2. Executa e captura o fluxo de pânico
    print(f"   🚀 Disparando incidente...")
    # Usamos timeout e garantimos a leitura completa
    try:
        proc = subprocess.run([exe_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
#        proc = subprocess.run([exe_path], capture_output=True, text=True, 
#                              encoding='utf-8', errors='replace', timeout=10)
        stdout_data = proc.stdout
        stderr_data = proc.stderr
    except subprocess.TimeoutExpired as e:
        stdout_data = e.stdout.decode() if e.stdout else ""
        stderr_data = e.stderr.decode() if e.stderr else ""
    
    # 3. Análise Forense
    forensic = SoteriaForensic()
    combined_output = proc.stdout + proc.stderr
#    combined_output = stdout_data + stderr_data
    
    if forensic.process_pipe(proc.stdout + proc.stderr):
        print(f"   ✅ [OK] Sotéria capturou o incidente com sucesso.")
        
        # Se for um erro fatal (como o null_test), o rescue.py deve ser chamado para o laudo
        if proc.returncode != 0:
            from doxoade.rescue import analyze_crash
            print(f"   🔎 Gerando Dossiê Lazarus (Exit: {proc.returncode})...")
            analyze_crash(proc.stdout + proc.stderr, exit_code=proc.returncode)
    else:
        print(f"   ⚠️  [REGRESSÃO] O sistema faliu ao identificar as TAGs forenses.")
        # Mostra o que saiu para debug
        if proc.stdout: print("--- STDOUT ---\n", proc.stdout)
        if proc.stderr: print("--- STDERR ---\n", proc.stderr)

if __name__ == "__main__":
    # Garante suporte a UTF-8 no Windows
    if sys.platform == 'win32': os.system('chcp 65001 > nul')
    
    print("🔥 [NEXUS DIAGNOSE] Iniciando Bateria de Testes de Regressão...")
    
    # Teste 1: Violação de Acesso (Ponteiro Nulo)
    testar_cenario("Ponteiro Nulo (AccessViolation)", "null_test.c")
    
    # Teste 2: Corrupção de Memória (Double Free)
    testar_cenario("Double Free (Heap Corruption)", "double_free_test.c")
    
    # Teste 3: Alinhamento SSE/AVX (Nova Funcionalidade v3)
    testar_cenario("Desalinhamento SSE", "align_test.c")

    # Teste 4: Uso após liberação
    testar_cenario("Dangling Pointer", "dangling_test.c")