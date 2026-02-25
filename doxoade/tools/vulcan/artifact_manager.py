# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/artifact_manager.py
"""
Gerencia artefatos nativos do Vulcan:
 - staging/ -> bin/ (promove somente se probe passar)
 - quarantine/ (mover binários inválidos)
 - logs simples em .doxoade/vulcan/logs/artifacts.log
Funções principais:
 - ensure_dirs(project_root)
 - promote_to_bin(project_root, pyd_path)
 - quarantine(project_root, pyd_path, reason)
 - probe_and_promote(project_root, module_name, pyd_path, python_exe=None, timeout=8)
"""
from pathlib import Path
import shutil
import subprocess
import os
import json
import time

LOG_NAME = "artifacts.log"

def _base(project_root: str) -> Path:
    return Path(project_root) / ".doxoade" / "vulcan"

def ensure_dirs(project_root: str):
    """Garante que as pastas do Vulcan (bin, staging, quarantine, logs) existam."""
    base = _base(project_root)
    for name in ("bin", "staging", "quarantine", "logs"):
        (base / name).mkdir(parents=True, exist_ok=True)

def _log(project_root: str, msg: str):
    """Registra uma ação no log de artefatos."""
    logs_dir = _base(project_root) / "logs"
    with open(logs_dir / "artifacts.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def promote_to_bin(project_root: str, pyd_path: Path):
    """Move um binário do staging para o diretório bin final."""
    ensure_dirs(project_root)
    dst = _base(project_root) / "bin" / pyd_path.name
    shutil.move(str(pyd_path), str(dst))
    _log(project_root, f"PROMOTED {pyd_path.name} -> bin/")
    return dst

def quarantine(project_root: str, pyd_path: Path, reason: str):
    """Move um binário inválido para quarentena."""
    ensure_dirs(project_root)
    dst = _base(project_root) / "quarantine" / pyd_path.name
    shutil.move(str(pyd_path), str(dst))
    _log(project_root, f"QUARANTINED {pyd_path.name} (Reason: {reason})")
    return dst
    
def _run_probe_subprocess(project_root: str, module_name: str) -> dict:
    """Executa a sonda de importação em um subprocesso seguro."""
    python_exe = sys.executable
    probe_script = Path(__file__).resolve().parent / "probe_import.py"
    if not probe_script.exists():
        return {"ok": False, "error": "probe_script_not_found"}

    env = os.environ.copy()
    # Adiciona a pasta bin do vulcan ao path do sistema para que o import encontre o binário
    bin_path = str(_base(project_root) / "bin")
    env["PYTHONPATH"] = os.pathsep.join([bin_path, env.get("PYTHONPATH", "")])

    cmd = [python_exe, str(probe_script), module_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=10, text=True, encoding="utf-8")
        result_data = json.loads(proc.stdout) if proc.stdout else {"ok": False, "error": proc.stderr}
        return result_data
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))} \033[0m")
        exc_trace(exc_tb)
        return {"ok": False, "error": f"Probe execution failed: {type(e).__name__}"}

def probe_and_promote(project_root: str, module_name: str, pyd_path: Path):
    """
    Roda a sonda no binário. Se passar, promove para 'bin'. Se falhar, para 'quarantine'.
    """
    # 1. Move para 'bin' temporariamente para que o import possa encontrá-lo
    promoted_path = promote_to_bin(project_root, pyd_path)

    # 2. Roda a sonda de verificação
    probe_result = _run_probe_subprocess(project_root, module_name)

    # 3. Decide o destino final com base no resultado
    if probe_result.get("ok"):
        _log(project_root, f"PROBE-OK: {module_name} is valid.")
        return {"ok": True, "action": "promoted", "path": str(promoted_path)}
    else:
        # Se a sonda falhou, move da pasta 'bin' para a 'quarantine'
        reason = probe_result.get("error", "unknown_probe_failure")
        quarantined_path = quarantine(project_root, promoted_path, str(reason))
        return {"ok": False, "action": "quarantined", "path": str(quarantined_path), "probe": probe_result}