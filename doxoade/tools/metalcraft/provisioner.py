# -*- coding: utf-8 -*-
import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path
from doxoade.tools.telemetry_tools.logger import chief_heartbeat

def download_w64devkit(target_path: Path):
    """Baixa e extrai os binários do w64devkit (Release v1.21.0)."""
    # URL da release binária estável que contém o .zip padrão
    url = "https://github.com/skeeto/w64devkit/releases/download/v1.21.0/w64devkit-1.21.0.zip"
    zip_tmp = target_path / "devkit.zip"
    
    chief_heartbeat("INFRA", "PROVISION_START", {"url": url, "target": str(target_path)})
    
    print(f"   📥 Baixando Toolchain Industrial v1.21.0 (85MB)...")
    try:
        # Configura um User-Agent para evitar bloqueios do GitHub em scripts
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, zip_tmp)
        
        print(f"   📦 Extraindo binários em {target_path.name}...")
        with zipfile.ZipFile(zip_tmp, 'r') as zip_ref:
            zip_ref.extractall(target_path)
        
        # O w64devkit extrai para uma pasta interna. Vamos mover para a raiz de thirdparty/w64devkit
        extracted_folder = target_path / "w64devkit"
        if extracted_folder.exists():
            for item in extracted_folder.iterdir():
                dest = target_path / item.name
                if dest.exists():
                    if dest.is_dir(): shutil.rmtree(dest)
                    else: dest.unlink()
                shutil.move(str(item), str(target_path))
            shutil.rmtree(extracted_folder)

        zip_tmp.unlink()
        chief_heartbeat("INFRA", "PROVISION_SUCCESS", {"status": "Compiler Ready"})
        return True
    except Exception as e:
        chief_heartbeat("INFRA", "PROVISION_FAILED", {"error": str(e)})
        print(f"   ❌ Falha no provisionamento: {e}")
        return False