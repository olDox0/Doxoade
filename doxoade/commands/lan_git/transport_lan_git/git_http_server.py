# doxoade/commands/lan_git/transport_lan_git/git_http_server.py
# Plano B: Servidor Git Smart HTTP embutido
""" Módulo Servidor Git Smart HTTP Embutido com Suporte a Espaços em Nomes de Silos. """

import os
import time
import subprocess
import traceback
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote
import click


def identify_peer_device(ip: str) -> str:
    if ip == "192.168.18.91":
        return "💻 PC-B (Windows 11)"
    elif ip == "192.168.18.105":
        return "📱 PC-C (Android / Termux)"
    elif ip.startswith("127.") or ip == "localhost":
        return "🖥️ Localhost (Self-Check)"
    return f"🌐 Dispositivo ({ip})"


class SecureGitHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP com suporte a unquote para caminhos com espaços."""

    repo_dir: str = ""
    repo_name: str = ""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        parsed = urlparse(self.path)
        if "git-receive-pack" in parsed.path:
            self.send_error(403, "Acesso Negado: Push Proibido.")
            return

        self._handle_git_backend("POST")

    def do_GET(self):
        self._handle_git_backend("GET")

    def _handle_git_backend(self, method: str):
        client_ip = self.client_address[0]
        device_label = identify_peer_device(client_ip)
        parsed = urlparse(self.path)
        
        # ⚡ Decodifica a URL (ex: "/Projeto%20SysUtils/..." -> "/Projeto SysUtils/...")
        unquoted_path = unquote(parsed.path)
        clean_path = os.path.normpath(unquoted_path).lstrip("/\\")

        if ".." in clean_path:
            self.send_error(400, "Caminho malicioso detectado.")
            return

        timestamp_str = time.strftime("%H:%M:%S")
        if "info/refs" in unquoted_path:
            click.secho(f"  [{timestamp_str}] [GIT-NEGOTIATE] {device_label} consultando referências...", fg="cyan")
        elif "git-upload-pack" in unquoted_path:
            click.secho(f"  [{timestamp_str}] [GIT-STREAM] Transmitindo pack de objetos para {device_label}...", fg="green")

        env = {
            "REQUEST_METHOD": method,
            "GIT_PROJECT_ROOT": os.path.dirname(self.repo_dir),
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": unquoted_path,
            "QUERY_STRING": parsed.query,
            "REMOTE_ADDR": client_ip,
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
                err_msg = res.stderr.decode('utf-8', errors='ignore')
                click.secho(f"  [{timestamp_str}] ✖ [BACKEND-ERR] {err_msg}", fg="red")
                self.send_error(500, f"Erro interno no backend do Git: {err_msg}")
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

            if "git-upload-pack" in unquoted_path:
                click.secho(f"  [{timestamp_str}] ✔ [STREAM-OK] Objetos entregues a {device_label} ({len(body)} bytes).", fg="green", bold=True)

        except Exception as e:
            tb = traceback.format_exc()
            click.secho(f"  [{timestamp_str}] ✖ [GIT-ERR] Falha ao atender {device_label}: {e}\n{tb}", fg="red")
            self.send_error(500, "Falha na execução do backend Git.")


class GitHTTPServer:
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