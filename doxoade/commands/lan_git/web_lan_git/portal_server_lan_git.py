# doxoade/commands/lan_git/web_lan_git/portal_server_lan_git.py
""" Módulo Servidor HTTP do Portal Web LAN Doxoade com SSE e Smart HTTP.
Implementa transmissão em tempo real (Push SSE), cache em RAM e proteção de concorrência. """

import os
import sys
import time
import shutil
import urllib.request
import tempfile
import threading
import queue
import json
import subprocess
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple, Set
import click

from doxoade.commands.lan_git.web_lan_git.auth_session_lan_git import LANAuthManager
from doxoade.commands.lan_git.web_lan_git.sanitizer_stream_lan_git import ProjectSanitizer
from doxoade.commands.lan_git.web_lan_git.bootstrap_generator_lan_git import BootstrapGenerator
from doxoade.commands.lan_git.web_lan_git.ui_templates_lan_git import UIPortalTemplates
from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifestExtractor
from doxoade.commands.lan_git.transport_lan_git.git_bundle_stream import GitBundleHost
from doxoade.commands.lan_git.transport_lan_git.fastpack_builder_lan_git import FastpackBuilder

# ═════════════════════════════════════════════════════════════════════
# PRODENOV: MOTOR DE TELEMETRIA E LATÊNCIA DE REDE (CAPÍTULO 2)
# ═════════════════════════════════════════════════════════════════════
class WebLatencyProfiler:
    """Coletor em memória de latência e throughput de requisições LAN."""
    
    def __init__(self):
        self.enabled = False
        self._lock = threading.Lock()
        self.request_times = []  # Lista de (rota, tempo_ms, status, bytes)
        self.sse_broadcast_times = []  # Tempos de push SSE em ms

    def record_request(self, path: str, duration_ms: float, status_code: int, bytes_sent: int):
        if not self.enabled:
            return
        with self._lock:
            self.request_times.append((path, duration_ms, status_code, bytes_sent))
            # Mantém histórico das últimas 1000 requisições
            if len(self.request_times) > 1000:
                self.request_times.pop(0)

    def record_broadcast(self, duration_ms: float, listeners_count: int):
        if not self.enabled:
            return
        with self._lock:
            self.sse_broadcast_times.append((duration_ms, listeners_count))
            if len(self.sse_broadcast_times) > 500:
                self.sse_broadcast_times.pop(0)

    def generate_report(self) -> str:
        with self._lock:
            if not self.request_times:
                return "Nenhuma métrica de rede registrada durante a sessão."
            
            durations = [t[1] for t in self.request_times]
            avg_lat = sum(durations) / len(durations)
            min_lat = min(durations)
            max_lat = max(durations)
            durations_sorted = sorted(durations)
            p95 = durations_sorted[int(len(durations_sorted) * 0.95)] if len(durations_sorted) >= 20 else max_lat
            total_bytes = sum(t[3] for t in self.request_times)

            sse_avg = 0.0
            if self.sse_broadcast_times:
                sse_avg = sum(b[0] for b in self.sse_broadcast_times) / len(self.sse_broadcast_times)

        lines = [
            "============================================================",
            "        📊 RELATÓRIO FORENSE DE PERFORMANCE (WEB LAN)",
            "============================================================",
            f"  Total de Requisições   : {len(durations)}",
            f"  Volume Trafegado       : {total_bytes / 1024:.2f} KB",
            f"  Latência Mínima        : {min_lat:.3f} ms",
            f"  Latência Média         : {avg_lat:.3f} ms",
            f"  Latência P95           : {p95:.3f} ms",
            f"  Latência Máxima        : {max_lat:.3f} ms",
            f"  Push SSE Médio (RAM)   : {sse_avg:.3f} ms",
            "============================================================"
        ]
        return "\n".join(lines)

class NotepadBroadcaster:
    """Gerenciador de Estado do Bloco de Notas em RAM com Push SSE (Plano A)."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.notes_file = os.path.join(repo_path, "shared_notes.md")
        self._lock = threading.Lock()
        self._revision = 1
        self._listeners: Set[queue.Queue] = set()
        self._content = self._load_from_disk()

    def _load_from_disk(self) -> str:
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def get_data(self) -> Tuple[str, int]:
        with self._lock:
            return self._content, self._revision

    def update_content(self, new_content: str) -> int:
        with self._lock:
            if new_content == self._content:
                return self._revision
            self._content = new_content
            self._revision += 1
            current_rev = self._revision
            listeners_snapshot = list(self._listeners)

        # 1. Notifica todos os ouvintes conectados via SSE em memória (< 1ms)
        t_broadcast_start = time.perf_counter_ns()
        payload = json.dumps({"text": new_content, "rev": current_rev, "ts": time.time()})
        msg = f"event: update\ndata: {payload}\n\n"
        for q in listeners_snapshot:
            try:
                q.put_nowait(msg)
            except Exception:
                pass
        t_broadcast_end = time.perf_counter_ns()
        broadcast_ms = (t_broadcast_end - t_broadcast_start) / 1_000_000.0
        
        if SecurePortalRequestHandler.profiler:
            SecurePortalRequestHandler.profiler.record_broadcast(broadcast_ms, len(listeners_snapshot))

        # 2. Persiste assincronamente no disco sem travar a resposta HTTP
        threading.Thread(target=self._persist_to_disk, args=(new_content,), daemon=True).start()
        return current_rev

    def _persist_to_disk(self, content: str):
        try:
            with open(self.notes_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            click.secho(f"  ✖ [DISK-PERSIST-ERR] Falha ao gravar shared_notes.md: {e}", fg="red")

    def register_listener(self) -> queue.Queue:
        q = queue.Queue(maxsize=32)
        with self._lock:
            self._listeners.add(q)
            # Envia o estado inicial
            payload = json.dumps({"text": self._content, "rev": self._revision})
            q.put_nowait(f"event: init\ndata: {payload}\n\n")
        return q

    def unregister_listener(self, q: queue.Queue):
        with self._lock:
            self._listeners.discard(q)


class SecurePortalRequestHandler(BaseHTTPRequestHandler):
    """Handler seguro para requisições web, Git Smart HTTP e Bloco de Notas LAN com SSE."""

    auth_manager: LANAuthManager = None
    repo_path: str = ""
    repo_name: str = ""
    host_ip: str = ""
    host_port: int = 8080
    broadcaster: NotepadBroadcaster = None

    def log_message(self, format, *args):
        msg = format % args
        client_ip = self.client_address[0]
        # Silencia logs repetitivos de SSE ou polling limpo para não poluir o terminal
        if "/api/notepad/events" in msg or " 304 " in msg:
            return
        if " 200 " in msg or " 302 " in msg:
            click.secho(f"  [HTTP] {client_ip} -> {msg}", fg="green")
        elif " 401 " in msg or " 429 " in msg:
            click.secho(f"  [AUTH-WARN] {client_ip} -> {msg}", fg="yellow")
        else:
            click.secho(f"  [HTTP-LOG] {client_ip} -> {msg}", fg="cyan")

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
        if self.auth_manager.validate_session(token, client_ip):
            return True

        auth_header = self.headers.get("Authorization")
        if self.auth_manager.validate_basic_auth(auth_header):
            return True

        return False

    def handle_one_request(self):
        """Interceptador ProDeNov contra tentativas de HTTPS e lixo binário."""
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.send_error(414)
                return

            if not self.raw_requestline:
                self.close_connection = True
                return

            # Triangulação de assinatura TLS (0x16 0x03)
            if len(self.raw_requestline) >= 3 and self.raw_requestline[0] == 0x16 and self.raw_requestline[1] == 0x03:
                client_ip = self.client_address[0]
                click.secho(f"  ⚠ [PRODENOV ALERTA] {client_ip} tentou conectar via HTTPS em porta HTTP pura.", fg="yellow", bold=True)
                click.secho(f"    👉 Acesse usando: http://{self.host_ip}:{self.host_port} (sem o 's')", fg="cyan")
                self.close_connection = True
                return

            if not self.parse_request():
                return

            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(501, f"Metodo nao suportado ({self.command})")
                return

            # Início da medição de alta precisão
            t_start = time.perf_counter_ns()
            
            method = getattr(self, mname)
            method()
            self.wfile.flush()
            
            # Fim da medição
            t_end = time.perf_counter_ns()
            duration_ms = (t_end - t_start) / 1_000_000.0
            
            if self.profiler and self.profiler.enabled:
                self.profiler.record_request(self.path, duration_ms, 200, 0)
                if self.path != "/api/notepad/events":
                    click.secho(f"    ⚡ [PERF] {self.command} {self.path} -> {duration_ms:.2f}ms", fg="magenta")

            self.wfile.flush()
        except (TimeoutError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True
        except Exception:
            self.close_connection = True

    def _handle_git_backend(self, method: str):
        auth_header = self.headers.get("Authorization")
        if not self.auth_manager.validate_basic_auth(auth_header):
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Doxoade LAN Git"')
            self.end_headers()
            self.wfile.write(b"Autenticacao Git necessaria.")
            return

        parsed = urlparse(self.path)
        env = {
            "REQUEST_METHOD": method,
            "GIT_PROJECT_ROOT": os.path.dirname(self.repo_path),
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
        except Exception as e:
            self.send_error(500, f"Falha no Git Backend: {e}")

    def do_GET(self):
        client_ip = self.client_address[0]
        host_header = self.headers.get("Host")

        if not self.auth_manager.validate_host_header(host_header, self.host_ip, self.host_port):
            self.send_response(400)
            self._inject_security_headers("text/plain")
            self.end_headers()
            self.wfile.write(b"400 Bad Request: Host Header Invalido.")
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if "info/refs" in path:
            self._handle_git_backend("GET")
            return

        if path in ("/", "/login"):
            if self._is_authenticated():
                self.send_response(302)
                self.send_header("Location", "/dashboard")
                self.end_headers()
                return

            allowed, attempts_left, remaining = self.auth_manager.check_rate_limit(client_ip)
            html = UIPortalTemplates.render_login_page(
                lockout_remaining=remaining if not allowed else 0,
                attempts_left=attempts_left
            )
            self.send_response(200)
            self._inject_security_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Barreira de Autenticação Estrita
        if not self._is_authenticated():
            if path != "/favicon.ico":
                click.secho(f"  [AUTH-BLOQUEIO] Tentativa não autenticada em '{path}' de {client_ip}.", fg="yellow")
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        repo_name = self.repo_name or os.path.basename(os.path.abspath(self.repo_path))

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

        elif path == "/notepad":
            content, _ = self.broadcaster.get_data()
            html = UIPortalTemplates.render_notepad(content, repo_name)
            self.send_response(200)
            self._inject_security_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        # ⚡ [PLANO A] STREAM SSE DE TRANSMISSÃO EM TEMPO REAL (< 5ms)
        elif path == "/api/notepad/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            q = self.broadcaster.register_listener()
            try:
                while True:
                    try:
                        # Aguarda mensagem do broadcaster com timeout para emitir keep-alive
                        msg = q.get(timeout=15.0)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive Ping para segurar a conexão aberta no roteador
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                self.broadcaster.unregister_listener(q)

        # 🟡 [PLANO B] LEITURA VIA CACHE EM RAM COM SUPORTE A 304 NOT MODIFIED
        elif path == "/api/notepad":
            query_params = parse_qs(parsed.query)
            client_rev = int(query_params.get("rev", [0])[0])
            content, current_rev = self.broadcaster.get_data()

            if client_rev > 0 and client_rev == current_rev:
                self.send_response(304)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("X-Notepad-Revision", str(current_rev))
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))

        elif path == "/download/fastpack":
            t0 = time.time()
            ok, fastpack_path, err = FastpackBuilder.get_or_build_fastpack_path(self.repo_path)
            if not ok or not fastpack_path or not os.path.exists(fastpack_path):
                self.send_response(500)
                self.end_headers()
                return

            dur = time.time() - t0
            file_size = os.path.getsize(fastpack_path)
            filename = f"{repo_name}_fastpack.pyz"

            self.send_response(200)
            self.send_header("Content-Type", "application/x-zip-compressed")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self._inject_security_headers("application/x-zip-compressed")
            self.end_headers()

            with open(fastpack_path, "rb") as f_in:
                shutil.copyfileobj(f_in, self.wfile, length=64 * 1024)
            click.secho(f"  ✔ [FASTPACK] {filename} entregue ({file_size/1024/1024:.2f} MB em {dur:.2f}s).", fg="green")

        elif path == "/download/zip":
            ok, zip_buf, err = ProjectSanitizer.build_sanitized_zip_buffer(self.repo_path)
            if not ok or not zip_buf:
                self.send_response(503)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{repo_name}.zip"')
            self._inject_security_headers("application/zip")
            self.end_headers()
            self.wfile.write(zip_buf.getvalue())

        elif path == "/download/bundle":
            with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                if GitBundleHost.create_bundle(self.repo_path, tmp_path):
                    with open(tmp_path, "rb") as f:
                        bundle_data = f.read()
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
        path = parsed.path
        client_ip = self.client_address[0]

        if "git-upload-pack" in path:
            self._handle_git_backend("POST")
            return

        if path == "/login":
            allowed, attempts_left, remaining = self.auth_manager.check_rate_limit(client_ip)
            if not allowed:
                click.secho(f"  [FAIL2BAN] IP {client_ip} bloqueado ({remaining}s restantes).", fg="red", bold=True)
                html = UIPortalTemplates.render_login_page(lockout_remaining=remaining, attempts_left=0)
                self.send_response(429)
                self._inject_security_headers()
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="ignore")
            params = parse_qs(body)
            password = params.get("password", [""])[0]

            if self.auth_manager.verify_password(password):
                self.auth_manager.record_successful_attempt(client_ip)
                token = self.auth_manager.create_session(client_ip)
                click.secho(f"  ✔ [AUTH] {client_ip} autenticado com sucesso.", fg="green", bold=True)

                self.send_response(302)
                self.send_header("Set-Cookie", f"dox_session={token}; Max-Age=3600; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Location", "/dashboard")
                self.end_headers()
            else:
                fail_num = self.auth_manager.record_failed_attempt(client_ip)
                attempts_left = max(0, self.auth_manager.max_attempts - fail_num)
                click.secho(f"  ⚠ [AUTH] IP {client_ip} errou a senha ({fail_num}/{self.auth_manager.max_attempts}).", fg="yellow", bold=True)
                html = UIPortalTemplates.render_login_page(
                    error_msg="Senha de acesso incorreta.",
                    attempts_left=attempts_left
                )
                self.send_response(401)
                self._inject_security_headers()
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            return

        # ⚡ ATUALIZAÇÃO REATIVA DO BLOCO DE NOTAS EM RAM + BROADCAST
        if path == "/api/notepad":
            if not self._is_authenticated():
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Nao autenticado.")
                return

            length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(length).decode("utf-8", errors="ignore")

            new_rev = self.broadcaster.update_content(content)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "rev": new_rev}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


class ThreadingHTTPServer(HTTPServer):
    """Servidor HTTP multithread nativo para suportar múltiplos streams SSE simultâneos."""
    def process_request(self, request, client_address):
        t = threading.Thread(target=self.process_request_thread, args=(request, client_address), daemon=True)
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

class LANWebPortal:
    """Gerenciador do ciclo de vida do Portal Web Local com SSE e Multithreading."""

    def __init__(self, repo_path: str, password: str, host_ip: str, port: int = 8080, profile: bool = False):
        self.repo_path = os.path.abspath(repo_path)
        self.password = password
        self.host_ip = host_ip
        self.port = port
        self.profile = profile
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.profiler = WebLatencyProfiler()
        self.profiler.enabled = profile

    def start(self) -> Tuple[bool, Optional[str]]:
        try:
            SecurePortalRequestHandler.profiler = self.profiler
            SecurePortalRequestHandler.auth_manager = LANAuthManager(self.password)
            SecurePortalRequestHandler.repo_path = self.repo_path
            SecurePortalRequestHandler.repo_name = os.path.basename(self.repo_path)
            SecurePortalRequestHandler.host_ip = self.host_ip
            SecurePortalRequestHandler.host_port = self.port
            SecurePortalRequestHandler.broadcaster = NotepadBroadcaster(self.repo_path)

            self.server = ThreadingHTTPServer(("0.0.0.0", self.port), SecurePortalRequestHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()

            self._run_self_probe()
            return True, None
        except Exception as e:
            return False, f"Falha ao vincular porta {self.port}: {e}"

    def _run_self_probe(self):
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
        if self.profiler and self.profiler.enabled:
            click.echo("\n" + self.profiler.generate_report() + "\n")
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
