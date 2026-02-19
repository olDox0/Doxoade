# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/recovery_engine.py
"""Motor de Recuperação Forense - Janela Segura (PASC 1.1 / Ma'at)."""
import os
import re
import shutil
from datetime import datetime
# [DOX-UNUSED] from pathlib import Path

def run_recovery_mission(backup_dir: str, output_dir: str):
    """Resgate travado antes da regressão de 14/02."""
    if not os.path.exists(backup_dir):
        return False, f"Caminho não encontrado: {backup_dir}"

    # Janela Segura: Fev/2026 até o último minuto de 13/02
    LIMIT_DATE = datetime(2026, 2, 14, 0, 0, 0)
# [DOX-UNUSED]     start_dt = datetime(2026, 2, 9, 0, 0, 0)
# [DOX-UNUSED]     end_dt = datetime(2026, 2, 14, 21, 0, 0)

    latest_versions = {}
    ts_pattern = re.compile(r"(.+)\.(\d{4}-\d{2}-\d{2}_\d{6})\.bak$")

    files = os.listdir(backup_dir)
    
    for file in files:
        file_path = os.path.join(backup_dir, file)
        file_dt = None
        original_name = None

        match = ts_pattern.match(file)
        if match:
            original_name = match.group(1)
            try:
                file_dt = datetime.strptime(match.group(2), "%Y-%m-%d_%H%M%S")
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: run_recovery_mission\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        
        if not file_dt and file.endswith('.bak'):
            original_name = file.replace('.bak', '')
            file_dt = datetime.fromtimestamp(os.path.getmtime(file_path))

        if original_name in latest_versions:
            current_best_dt, _ = latest_versions[original_name]
            if file_dt > current_best_dt and file_dt < LIMIT_DATE:
                latest_versions[original_name] = (file_dt, file_path)
        elif file_dt < LIMIT_DATE:
            latest_versions[original_name] = (file_dt, file_path)

    if not latest_versions:
        return False, "Nenhum material estável encontrado antes de 14/02."

    os.makedirs(output_dir, exist_ok=True)
    for name, (dt, path) in latest_versions.items():
        dest = os.path.join(output_dir, name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)
    
    return True, f"Sucesso: {len(latest_versions)} arquivos estáveis resgatados em: {output_dir}"