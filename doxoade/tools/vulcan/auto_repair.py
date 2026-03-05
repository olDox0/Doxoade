# doxoade/tools/vulcan/auto_repair.py
import os
import sys
import subprocess
import shutil
import json
import time
from pathlib import Path

from doxoade.tools.vulcan.abi_gate import run_abi_gate
from doxoade.tools.vulcan.compiler_safe import compile_module
from doxoade.tools.vulcan.artifact_manager import probe_and_promote

PROBE_SCRIPT = Path(__file__).resolve().parent / "probe_import.py"

def _vulcan_base(project_root: str) -> Path:
    return Path(project_root) / ".doxoade" / "vulcan"

def _staging_dir(project_root: str) -> Path:
    return _vulcan_base(project_root) / "staging"

def _bin_dir(project_root: str) -> Path:
    return _vulcan_base(project_root) / "bin"

def _quarantine_dir(project_root: str) -> Path:
    return _vulcan_base(project_root) / "quarantine"

def _ensure_dirs(project_root: str):
    for d in (_staging_dir(project_root), _bin_dir(project_root), _quarantine_dir(project_root)):
        d.mkdir(parents=True, exist_ok=True)

def _log(project_root: str, msg: str):
    base = _vulcan_base(project_root)
    logs = base / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / "auto_repair.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def _promote(proj_root: str, pyd_path: Path):
    bin_dir = _bin_dir(proj_root)
    dst = bin_dir / pyd_path.name
    shutil.move(str(pyd_path), str(dst))
    return dst

def _quarantine(proj_root: str, pyd_path: Path, reason: str):
    qdir = _quarantine_dir(proj_root)
    dst = qdir / pyd_path.name
    shutil.move(str(pyd_path), str(dst))
    _log(proj_root, f"quarantined {pyd_path.name} reason={reason}")
    return dst

def _validate_import_in_subprocess(project_root: str, module_name: str, python_exe: str = None, timeout: int = 10):
    python_exe = python_exe or sys.executable
    env = os.environ.copy()
    project_root_abs = str(Path(project_root).resolve())
    env["PYTHONPATH"] = os.pathsep.join([project_root_abs, env.get("PYTHONPATH", "")])
    cmd = [python_exe, str(PROBE_SCRIPT), module_name]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=timeout, text=True)
        out = (proc.stdout or "").strip()
        try:
            j = json.loads(out) if out else {}
        except Exception as e:
            print(f"\033[31m ■ Erro: {e}")
            j = {"ok": False, "error": "invalid_probe_output", "stdout": out, "stderr": proc.stderr}
        j["_returncode"] = proc.returncode
        j["_stderr"] = proc.stderr
        return j
    except subprocess.TimeoutExpired as e:
        print(f"\033[31m ■ Erro: {e}")
        return {"ok": False, "error": "timeout", "details": str(e)}

def _guess_module_src_dirs(project_root: str, module_name: str) -> list[Path]:
    """
    Heurística para adivinhar onde está o código fonte:
      - project_root/<last>
      - project_root/doxoade/tools/<last>
      - project_root/doxoade/<last>
    """
    last = module_name.split(".")[-1]
    root = Path(project_root)
    candidates = [
        root / last,
        root / "doxoade" / "tools" / last,
        root / "doxoade" / last,
        root
    ]
    # remove duplicates and non-existant later
    seen = []
    out = []
    for c in candidates:
        rc = c.resolve() if c.exists() else c
        if str(rc) not in seen:
            seen.append(str(rc))
            out.append(c)
    return out

def auto_repair_module(project_root: str, module_name: str, module_src_dir: str = None, retries: int = 1, python_exe: str = None):
    _ensure_dirs(project_root)
    python_exe = python_exe or sys.executable

    report = {"module": module_name, "attempts": [], "final": None}

    # resolve module_src_dir
    if module_src_dir:
        src = Path(module_src_dir)
        if not src.is_absolute():
            src = Path(project_root) / src
        if not src.exists():
            raise FileNotFoundError(f"Provided module_src_dir does not exist: {src}")
        candidate_dirs = [src]
    else:
        candidate_dirs = _guess_module_src_dirs(project_root, module_name)

    # Try each candidate path and retry cycles
    attempt_no = 0
    for candidate in candidate_dirs:
        for attempt in range(1, retries + 2):
            attempt_no += 1
            step = {"attempt": attempt_no, "time": time.time(), "actions": []}
            try:
                # ensure candidate exists
                if not candidate.exists():
                    step["exception"] = f"candidate path does not exist: {candidate}"
                    report["attempts"].append(step)
                    _log(project_root, step["exception"])
                    break  # go to next candidate

                # build into staging
                step["actions"].append(f"compile {candidate} -> staging")
                try:
                    moved = compile_module(candidate, _staging_dir(project_root), project_root=Path(project_root)) #noqa
                except Exception as e:
                    print(f"\033[31m ■ Erro: {e}")
                    step["exception"] = f"compile_failed: {e}"
                    report["attempts"].append(step)
                    _log(project_root, step["exception"])
                    # retry if attempts left
                    continue

                # ABI Gate
                step["actions"].append("run abi_gate")
                run_abi_gate(project_root)

                # select candidate artifact in bin
                stem = module_name.split(".")[-1]
                ext = ".pyd" if os.name == "nt" else ".so"
                bin_dir = _bin_dir(project_root)
                candidates_found = sorted(bin_dir.glob(f"v_{stem}*{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
                if not candidates_found:
                    step["actions"].append("no candidate found in bin after gate")
                    report["attempts"].append(step)
                    _log(project_root, "no promoted candidate found; continuing")
                    continue

                chosen = candidates_found[0]
                step["actions"].append(f"promoted_candidate={chosen.name}")

                # probe import
                step["actions"].append("probe_import subprocess check")
                probe_res = _validate_import_in_subprocess(project_root, module_name, python_exe=python_exe)
                step["probe"] = probe_res

                res = probe_and_promote(project_root, module_name, Path(str(chosen)), python_exe=python_exe, timeout=12)
                if res.get("ok"):
                    # promovido com sucesso; res['path'] é o arquivo em bin/
                    _log(project_root, f"auto_repair: promoted {res.get('path')}")
                    report["final"] = {"status": "ok", "chosen": Path(res.get("path")).name, "probe": res.get("probe")}
                    return report
                else:
                    # já foi quarentenado pelo artifact_manager; registre e prossiga (tentar outro candidate/retry)
                    _log(project_root, f"auto_repair: artifact quarantined reason={res.get('probe')}")


            except Exception as e:
                print(f"\033[31m ■ Erro: {e}")
                step["exception"] = str(e)
                report["attempts"].append(step)
                _log(project_root, f"auto_repair exception module={module_name} exc={e}")
                continue

    # se esgotaram candidatos/attempts
    report["final"] = {"status": "failed", "attempts": len(report["attempts"])}
    return report