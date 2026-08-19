# doxoade/commands/lan_git/transport_lan_git/git_daemon_server.py
# Plano A: Wrapper do 'git daemon' nativo
""" Módulo Servidor Git Daemon Nativo (Plano A).
Executa o processo 'git daemon' com blindagem estrita para caminhos com espaços no Windows. """

import os
import subprocess
import time
from typing import Optional, Tuple


class GitDaemonServer:
    """Gerencia o processo do 'git daemon' com suporte a caminhos com espaços."""

    def __init__(self, repo_path: str, port: int = 9418):
        self.repo_path = os.path.abspath(repo_path)
        self.base_dir = os.path.dirname(self.repo_path)
        self.repo_name = os.path.basename(self.repo_path)
        self.port = port
        self.process: Optional[subprocess.Popen] = None

    def _sanitize_environment(self) -> bool:
        if not os.path.exists(self.repo_path):
            return False
        git_dir = os.path.join(self.repo_path, ".git")
        return os.path.isdir(git_dir) or self.repo_path.endswith(".git")

    def start(self) -> Tuple[bool, Optional[str]]:
        if not self._sanitize_environment():
            return False, f"Caminho inválido ou não é um repositório Git: {self.repo_path}"

        export_marker = os.path.join(self.repo_path, ".git", "git-daemon-export-ok")
        if not os.path.exists(export_marker):
            try:
                open(export_marker, "a").close()
            except Exception as e:
                return False, f"Falha ao criar marcador de segurança: {e}"

        base_dir_posix = self.base_dir.replace("\\", "/")
        repo_path_posix = self.repo_path.replace("\\", "/")

        # Removemos o --base-path com espaço e usamos argumentos separados limpos
        cmd = [
            "git", "daemon",
            "--reuseaddr",
            "--listen=0.0.0.0",
            "--export-all",
            "--enable=upload-pack",
            "--disable=receive-pack",
            f"--port={self.port}",
            f"--base-path={base_dir_posix}",
            repo_path_posix
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
            time.sleep(0.3)
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                return False, f"Erro ao iniciar git daemon: {err.decode('utf-8', errors='ignore')}"
            return True, None
        except Exception as e:
            return False, f"Falha ao executar 'git daemon': {e}"

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None