# doxoade/tools/npp_integration.py
import json
import os
import subprocess
from .display import Fore, Style

def signal_notepadpp(file_path, findings, project_root):
    """
    Sinaliza ao Notepad++ os achados de uma análise.
    PASC 8.7: Contrato de comunicação via JSON Atômico.
    """
    bridge_file = os.path.join(project_root, ".doxoade", "npp_bridge.json")
    
    # PASC 1.3: Garantir diretório de metadados
    os.makedirs(os.path.dirname(bridge_file), exist_ok=True)

    payload = {
        "source": os.path.abspath(file_path),
        "timestamp": os.getpid(), # ID do processo para unicidade
        "findings": [
            {"line": f.get('line'), "msg": f.get('message'), "sev": f.get('severity')}
            for f in findings if f.get('line')
        ]
    }

    # Escrita Atômica (Segurança contra corrupção)
    temp_bridge = bridge_file + ".tmp"
    with open(temp_bridge, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    os.replace(temp_bridge, bridge_file)

    # Invoca o N++ para focar no arquivo e na primeira linha de erro
    # Chief-Gold: Posicionamento instantâneo
    if payload["findings"]:
        first_err = payload["findings"][0]["line"]
        try:
            # Tenta localizar o executável via PATH
            subprocess.Popen(["notepad++", "-n" + str(first_err), payload["source"]])
        except FileNotFoundError:
            # Fallback silencioso conforme PASC 8.9
            pass