# doxoade/commands/lan_git/web_lan_git/portal_server_lan_git.py
# Servidor HTTP seguro, roteador de endpoints e headers defensivos
""" Módulo Servidor HTTP do Portal Web LAN Doxoade.
Inclui streaming direto de arquivos em disco (zero RAM overhead) e diagnóstico visual. """

import os
import sys
import time
import shutil
import urllib.request
import tempfile
import threading
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple
import click

from doxoade.commands.lan_git.web_lan_git.auth_session_lan_git import LANAuthManager
from doxoade.commands.lan_git.web_lan_git.sanitizer_stream_lan_git import ProjectSanitizer
from doxoade.commands.lan_git.web_lan_git.bootstrap_generator_lan_git import BootstrapGenerator
from doxoade.commands.lan_git.web_lan_git.ui_templates_lan_git import UIPortalTemplates
from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifestExtractor
from doxoade.commands.lan_git.transport_lan_git.git_bundle_stream import GitBundleHost
from doxoade.commands.lan_git.transport_lan_git.fastpack_builder_lan_git import FastpackBuilder


class SecurePortalRequestHandler(BaseHTTPRequestHandler):
    """Handler seguro para requisições web com streaming em disco e telemetria."""

    auth_manager: LANAuthManager = None
    repo_path: str = ""
    host_ip: str = ""
    host_port: int = 8080

    def log_message(self, format, *args):
        msg = format % args
        client_ip = self.client_address[0]
        if " 200 " in msg or " 302 " in msg:
            click.secho(f"  [HTTP] {client_ip} -> {msg}", fg="green")
        elif " 401 " in msg or " 429 " in msg:
            click.secho(f"  [AUTH-WARN] {client_ip} -> {msg}", fg="yellow")
        else:
            click.secho(f"  [HTTP-ERR] {client_ip} -> {msg}", fg="red")

    def _inject_security_headers(self, content_type: str = "text/html; charset=utf-8"):
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")

    def _get_session_token_from_cookie(self) -> Optional[str]:
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        for item in cookie_header.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                if k == "dox_session":
                    return v
        return None

    def _is_authenticated(self) -> bool:
        token = self._get_session_token_from_cookie()
        client_ip = self.client_address[0]
        return self.auth_manager.validate_session(token, client_ip)

    def do_GET(self):
        client_ip = self.client_address[0]
        host_header = self.headers.get("Host")

        # 1. Anti-DNS Rebinding
        if not self.auth_manager.validate_host_header(host_header, self.host_ip, self.host_port):
            click.secho(f"  [SECURITY] Host Header inválido rejeitado: '{host_header}' de {client_ip}", fg="red")
            self.send_response(400)
            self._inject_security_headers("text/plain")
            self.end_headers()
            self.wfile.write(b"400 Bad Request: Host Header Invalido.")
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # Rota de Login / Raiz
        if path in ("/", "/login"):
            if self._is_authenticated():
                self.send_response(302)
                self.send_header("Location", "/dashboard")
                self.end_headers()
                return

            allowed, remaining = self.auth_manager.check_rate_limit(client_ip)
            html = UIPortalTemplates.render_login_page(lockout_remaining=remaining if not allowed else 0)
            
            self.send_response(200)
            self._inject_security_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Rotas Protegidas
        if not self._is_authenticated():
            click.secho(f"  [AUTH] Acesso não autenticado a '{path}' por {client_ip}. Redirecionando...", fg="yellow")
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if path == "/dashboard":
            manifest = GitManifestExtractor.extract(self.repo_path, self.host_ip, self.host_port)
            if not manifest:
                self.send_response(500)
                self.end_headers()
                return

            html = UIPortalTemplates.render_dashboard(
                manifest.repo_name, manifest.branch, manifest.short_commit,
                manifest.commit_message, self.host_ip, self.host_port
            )
            self.send_response(200)
            self._inject_security_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif path == "/download/fastpack":
            click.secho(f"  [FASTPACK] Forjando/Recuperando FastPack (.pyz) para {client_ip}...", fg="cyan")
            t0 = time.time()
            ok, fastpack_path, err = FastpackBuilder.get_or_build_fastpack_path(self.repo_path)
            
            if not ok or not fastpack_path or not os.path.exists(fastpack_path):
                click.secho(f"  ✖ [FASTPACK-ERR] {err}", fg="red")
                self.send_response(500)
                self._inject_security_headers("text/plain")
                self.end_headers()
                self.wfile.write(f"Erro ao forjar FastPack: {err}".encode("utf-8"))
                return

            dur = time.time() - t0
            file_size = os.path.getsize(fastpack_path)
            repo_name = os.path.basename(os.path.abspath(self.repo_path))
            filename = f"{repo_name}_fastpack.pyz"

            self.send_response(200)
            self.send_header("Content-Type", "application/x-zip-compressed")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self._inject_security_headers("application/x-zip-compressed")
            self.end_headers()

            with open(fastpack_path, "rb") as f_in:
                shutil.copyfileobj(f_in, self.wfile, length=64 * 1024)

            click.secho(f"  ✔ [FASTPACK] {filename} entregue a {client_ip} ({file_size/1024/1024:.2f} MB em {dur:.2f}s).", fg="green")

        elif path == "/download/zip":
            click.secho(f"  [STREAM] Iniciando empacotamento ZIP para {client_ip}...", fg="cyan")
            ok, zip_buf, err = ProjectSanitizer.build_sanitized_zip_buffer(self.repo_path)
            if not ok or not zip_buf:
                self.send_response(503)
                self._inject_security_headers("text/plain")
                self.end_headers()
                self.wfile.write(f"Erro: {err}".encode("utf-8"))
                return

            repo_name = os.path.basename(os.path.abspath(self.repo_path))
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{repo_name}.zip"')
            self._inject_security_headers("application/zip")
            self.end_headers()
            self.wfile.write(zip_buf.getvalue())
            click.secho(f"  ✔ [STREAM] ZIP entregue com sucesso a {client_ip}.", fg="green")

        elif path == "/download/bootstrap":
            repo_name = os.path.basename(os.path.abspath(self.repo_path))
            bat_script = BootstrapGenerator.generate_windows_bat(repo_name, self.host_ip, self.host_port)

            self.send_response(200)
            self.send_header("Content-Type", "application/x-bat")
            self.send_header("Content-Disposition", 'attachment; filename="instalar_doxoade.bat"')
            self._inject_security_headers("application/x-bat")
            self.end_headers()
            self.wfile.write(bat_script.encode("utf-8"))

        elif path == "/download/bundle":
            with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                if GitBundleHost.create_bundle(self.repo_path, tmp_path):
                    with open(tmp_path, "rb") as f:
                        bundle_data = f.read()

                    repo_name = os.path.basename(os.path.abspath(self.repo_path))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="{repo_name}.bundle"')
                    self._inject_security_headers("application/octet-stream")
                    self.end_headers()
                    self.wfile.write(bundle_data)
                else:
                    self.send_response(500)
                    self.end_headers()
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

        elif path == "/logout":
            token = self._get_session_token_from_cookie()
            if token:
                self.auth_manager.invalidate_session(token)
            self.send_response(302)
            self.send_header("Set-Cookie", "dox_session=deleted; Max-Age=0; Path=/; HttpOnly; SameSite=Strict")
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        client_ip = self.client_address[0]

        if parsed.path == "/login":
            allowed, remaining = self.auth_manager.check_rate_limit(client_ip)
            if not allowed:
                click.secho(f"  [FAIL2BAN] IP {client_ip} bloqueado temporariamente ({remaining}s).", fg="red")
                html = UIPortalTemplates.render_login_page(lockout_remaining=remaining)
                self.send_response(429)
                self._inject_security_headers()
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            password = params.get("password", [""])[0]

            if self.auth_manager.verify_password(password):
                self.auth_manager.record_successful_attempt(client_ip)
                token = self.auth_manager.create_session(client_ip)
                click.secho(f"  ✔ [AUTH] Autenticação bem-sucedida de {client_ip}.", fg="green")

                self.send_response(302)
                self.send_header("Set-Cookie", f"dox_session={token}; Max-Age=3600; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/dashboard")
                self.end_headers()
            else:
                self.auth_manager.record_failed_attempt(client_ip)
                click.secho(f"  ✖ [AUTH] Senha incorreta recebida de {client_ip}.", fg="yellow")
                html = UIPortalTemplates.render_login_page(error_msg="Senha de acesso incorreta.")
                self.send_response(401)
                self._inject_security_headers()
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))


class LANWebPortal:
    """Gerenciador do ciclo de vida do Portal Web Local com Auto-Diagnóstico."""

    def __init__(self, repo_path: str, password: str, host_ip: str, port: int = 8080):
        self.repo_path = os.path.abspath(repo_path)
        self.password = password
        self.host_ip = host_ip
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[bool, Optional[str]]:
        try:
            SecurePortalRequestHandler.auth_manager = LANAuthManager(self.password)
            SecurePortalRequestHandler.repo_path = self.repo_path
            SecurePortalRequestHandler.host_ip = self.host_ip
            SecurePortalRequestHandler.host_port = self.port

            self.server = HTTPServer(("0.0.0.0", self.port), SecurePortalRequestHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()

            self._run_self_probe()
            return True, None
        except Exception as e:
            return False, f"Falha ao vincular porta {self.port}: {e}"

    def _run_self_probe(self):
        """Executa um probe HTTP local para certificar que o socket está ouvindo."""
        def probe():
            try:
                url = f"http://127.0.0.1:{self.port}/"
                req = urllib.request.Request(url, headers={"Host": "localhost"})
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        click.secho(f"  ✔ [SELF-CHECK] Servidor respondendo internamente com sucesso.", fg="green")
            except Exception:
                pass
        threading.Thread(target=probe, daemon=True).start()

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None