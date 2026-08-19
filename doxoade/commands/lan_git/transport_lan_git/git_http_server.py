# doxoade/commands/lan_git/transport_lan_git/git_http_server.py
# Plano B: Servidor Git Smart HTTP embutido
""" Módulo Servidor Git Smart HTTP Embutido (Plano B).
Servidor HTTP leve para transmissão resiliente e imune a bugs de caminho no Windows. """

import os
import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Tuple
from urllib.parse import urlparse


class SecureGitHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP customizado para o backend nativo do Git."""

    repo_dir: str = ""
    repo_name: str = ""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        # Permite upload-pack (leitura) e bloqueia receive-pack (escrita)
        parsed = urlparse(self.path)
        if "git-receive-pack" in parsed.path:
            self.send_error(403, "Acesso Negado: Push Proibido.")
            return

        self._handle_git_backend("POST")

    def do_GET(self):
        self._handle_git_backend("GET")

    def _handle_git_backend(self, method: str):
        parsed = urlparse(self.path)
        clean_path = os.path.normpath(parsed.path).lstrip("/\\")

        if ".." in clean_path:
            self.send_error(400, "Caminho malicioso detectado.")
            return

        env = {
            "REQUEST_METHOD": method,
            "GIT_PROJECT_ROOT": os.path.dirname(self.repo_dir),
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": parsed.path,
            "QUERY_STRING": parsed.query,
            "REMOTE_ADDR": self.client_address[0],
            "CONTENT_TYPE": self.headers.get("Content-Type", "")
        }

        try:
            body_input = b""
            if method == "POST":
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    body_input = self.rfile.read(length)

            res = subprocess.run(
                ["git", "http-backend"],
                env={**os.environ, **env},
                input=body_input,
                capture_output=True,
                timeout=30
            )

            if res.returncode != 0:
                self.send_error(500, f"Erro interno no backend do Git: {res.stderr.decode('utf-8', errors='ignore')}")
                return

            header_data, _, body = res.stdout.partition(b"\r\n\r\n")
            if not header_data:
                header_data, _, body = res.stdout.partition(b"\n\n")

            self.send_response(200)
            for line in header_data.splitlines():
                if b":" in line:
                    k, v = line.split(b":", 1)
                    self.send_header(k.decode("utf-8").strip(), v.decode("utf-8").strip())
            self.end_headers()
            self.wfile.write(body)

        except Exception:
            self.send_error(500, "Falha na execução do backend Git.")


class GitHTTPServer:
    """Gerenciador do ciclo de vida do Servidor Smart HTTP."""

    def __init__(self, repo_path: str, port: int = 8080):
        self.repo_path = os.path.abspath(repo_path)
        self.repo_name = os.path.basename(self.repo_path)
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[bool, Optional[str]]:
        try:
            SecureGitHTTPRequestHandler.repo_dir = self.repo_path
            SecureGitHTTPRequestHandler.repo_name = self.repo_name

            self.server = HTTPServer(("0.0.0.0", self.port), SecureGitHTTPRequestHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            return True, None
        except Exception as e:
            return False, f"Falha ao iniciar servidor HTTP na porta {self.port}: {e}"

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None