# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/core_locator.py
"""
📡 THE BEACON (Core Locator) - v1.0
Sistema de Posicionamento Global do Núcleo Doxoade.
Garante que o banco de dados global e os logs de telemetria 
sempre residam no diretório de instalação real do Doxoade, 
independentemente de onde o comando foi executado (os.getcwd).
"""
import os
import json
from pathlib import Path

# 1. 📡 DETECÇÃO ABSOLUTA (The Beacon)
# Este arquivo está em: doxoade/tools/core_locator.py
# parents[0] = tools | parents[1] = doxoade (package) | parents[2] = Repo/Install Root
_DETECTED_CORE_ROOT = Path(__file__).resolve().parents[2]

# 2. 💾 PERSISTÊNCIA GLOBAL (O Cofre de Memória)
# Salvamos o manifesto na Home do usuário para acesso rápido e cross-session
_GLOBAL_DOXOADE_DIR = Path.home() / ".doxoade"
_MANIFEST_PATH = _GLOBAL_DOXOADE_DIR / "core_manifest.json"

def _discover_and_save_manifest():
    """Descobre o caminho real do núcleo e o sela no manifesto global."""
    _GLOBAL_DOXOADE_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "core_root": str(_DETECTED_CORE_ROOT),
        "global_data_dir": str(_DETECTED_CORE_ROOT / "data"),
        "global_db_file": str(_DETECTED_CORE_ROOT / "data" / "doxoade.db"),
        "beacon_version": "1.0"
    }
    
    try:
        with open(_MANIFEST_PATH, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=4)
    except Exception:
        pass # Falha silenciosa: se não puder salvar, usamos a detecção em memória
        
    return manifest

def get_core_manifest():
    """Lê o manifesto persistido. Se estiver corrompido ou o caminho mudou, recalibra."""
    if _MANIFEST_PATH.exists():
        try:
            with open(_MANIFEST_PATH, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                # Validação de Integridade: O caminho ainda existe?
                if Path(manifest["core_root"]).exists():
                    return manifest
        except Exception:
            pass
    
    # Recalibragem automática
    return _discover_and_save_manifest()

# 3. 🏛️ EXPORTAÇÃO DE CONSTANTES GLOBAIS (Hades Lock)
_MANIFEST = get_core_manifest()

CORE_ROOT = Path(_MANIFEST["core_root"])
GLOBAL_DATA_DIR = Path(_MANIFEST["global_data_dir"])
GLOBAL_DB_FILE = Path(_MANIFEST["global_db_file"])

# Garante que o diretório de dados do núcleo exista fisicamente
GLOBAL_DATA_DIR.mkdir(parents=True, exist_ok=True)