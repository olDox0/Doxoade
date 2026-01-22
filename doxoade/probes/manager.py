# doxoade/probes/manager.py
import subprocess
# [DOX-UNUSED] import sys
import os
import json
from typing import Optional, Dict, Any

class ProbeManager:
    """Gerenciador Central de Execução de Sondas (Protocolo Aegis)."""
    def __init__(self, python_exe: str, project_root: str):
        self.python_exe = python_exe
        self.project_root = project_root
        self.env = os.environ.copy()
        # Garante que as sondas achem o pacote doxoade
        self.env["PYTHONPATH"] = str(project_root) + os.pathsep + self.env.get("PYTHONPATH", "")

    def execute(self, probe_script_path: str, target_file: Optional[str] = None, 
                payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executa uma sonda e garante integridade absoluta do retorno."""
        cmd = [self.python_exe, probe_script_path]
        if target_file:
            cmd.append(target_file)

        input_str = json.dumps(payload) if payload else "" 

        try:
            process = subprocess.run(
                cmd, input=input_str, capture_output=True, text=True,
                encoding='utf-8', errors='replace', env=self.env, shell=False,
                timeout=15
            )
            
            is_linter_report = process.returncode == 1 and process.stdout.strip() and "Traceback" not in process.stderr
            
            if process.returncode != 0 and not is_linter_report:
                return {
                    "success": False,
                    "error": process.stderr.strip() or f"Exit {process.returncode}",
                    "stdout": process.stdout
                }
            
            return {"success": True, "stdout": process.stdout, "error": None}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "TIMEOUT: Sonda demorou demais e foi encerrada.", "stdout": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": ""}