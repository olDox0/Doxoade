import subprocess
import shutil
import os
from pathlib import Path

def audit_binary_symbols(exe_path: str):
    """Verifica se o binário contém o DNA da Sotéria."""
    nm_path = shutil.which("nm") or shutil.which("nm.exe")
    if not nm_path:
        return {"ok": False, "error": "nm.exe não encontrado no PATH."}

    print(f"🔬 [NECROPSIA] Analisando símbolos de: {os.path.basename(exe_path)}")
    
    try:
        # Extrai a lista de símbolos do executável
        res = subprocess.run([nm_path, exe_path], capture_output=True, text=True)
        symbols = res.stdout
        
        dna_checks = {
            "SOTERIA_CORE": "soteria_init",
            "VACCINE_MARK": "soteria_mark_var",
            "ARENA_ENGINE": "g_arena_log",
            "EXCEPTION_GATE": "soteria_exception_handler"
        }
        
        results = {}
        for label, sym in dna_checks.items():
            present = sym in symbols
            results[label] = present
            status = "✅ PRESENTE" if present else "❌ AUSENTE"
            print(f"   • {label:<15}: {status}")
            
        return results
    except Exception as e:
        return {"ok": False, "error": str(e)}