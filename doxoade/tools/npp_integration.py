# -*- coding: utf-8 -*-
# doxoade/tools/npp_integration.py
import json
import os
import time

def signal_notepadpp(file_path: str, findings: list, project_root: str):
    """
    Exporta achados para o bridge JSON.
    Este código roda no terminal (Doxoade).
    """
    bridge_dir = os.path.join(project_root, ".doxoade")
    bridge_file = os.path.join(bridge_dir, "npp_bridge.json")
    
    if not os.path.exists(bridge_dir):
        os.makedirs(bridge_dir, exist_ok=True)

    payload = {
        "protocol": "Doxoade-NPP-v1",
        "source": os.path.abspath(file_path).replace("\\", "/"),
        "timestamp": time.time(),
        "findings": [
            {
                "line": f.get('line', 0),
                "msg": f.get('message', 'No message'),
                "sev": f.get('severity', 'WARNING')
            } for f in findings if f.get('line', 0) > 0
        ]
    }

    # Escrita Atômica
    temp_file = bridge_file + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_file, bridge_file)