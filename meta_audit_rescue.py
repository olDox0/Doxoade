# meta_audit_rescue.py
import subprocess, re, json
from doxoade.rescue import analyze_crash

def meta_audit():
    print("🔬 [META-AUDIT] Iniciando Rastreio de I/O do Rescue...")
    
    # 1. Captura o Output Bruto do Binário
    cmd = ["doxoade", "metal", "run", "race_test"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    raw_output = proc.stdout + proc.stderr
    
    print("\n--- [PASSO 1: RAW DATA FROM C] ---")
    tags_found = re.findall(r"TAG_(\w+): (.*)", raw_output)
    for tag, val in tags_found:
        print(f"  Captured Tag: {tag} = {val}")

    if not tags_found:
        print("  ❌ FALHA: O binário C não emitiu nenhuma TAG Sotéria.")

    # 2. Testa o Processamento do Lazarus (Rescue)
    print("\n--- [PASSO 2: LAZARUS INTERPRETATION] ---")
    dossier = analyze_crash(raw_output, exit_code=proc.returncode)
    
    print(f"  Interpretado como Erro: {dossier['technical_error']}")
    print(f"  Interpretado como File: {dossier['file']}")
    print(f"  Interpretado como Line: {dossier['line']}")

    # 3. Identifica a Causa da Regressão "A"
    if dossier['file'] == "A" or len(dossier['file']) <= 1:
        print("\n🚨 [DETECTADO] Bug de Path-Slicing no Rescue!")
        print(f"  O Rescue recebeu o path original: {dict(tags_found).get('RASTRO_LOC')}")
        print("  Mas a função _find_production_source ou o split o corrompeu.")

if __name__ == "__main__":
    meta_audit()