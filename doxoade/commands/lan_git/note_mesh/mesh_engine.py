# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_engine.py
"""
🌐 DOXNOTE MESH ENGINE v5.0 — PULL-ONLY MODE (Zero-Firewall-Dependency).
Modo soberano que NUNCA tenta push direto. Usa APENAS Auto-Pull via Beacon UDP.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import os
import sys
import time
import json
import socket
import select
import hashlib
import hmac
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse, parse_qs, quote
from typing import Optional, Dict, Any, List

MESH_MAGIC = "DOX_MESH_V5"
UDP_PORT = 54547
TCP_PORT = 54548


class MeshSyncHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP com suporte a GET (Auto-Pull) e POST (compatibilidade)."""
    engine: NoteMeshEngine = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        """Atende requisições de Auto-Pull do peer."""
        parsed = urlparse(self.path)
        if parsed.path == "/sync" and "fetch=" in parsed.query:
            qs = parse_qs(parsed.query)
            rel_path = qs.get("fetch", ["shared_notes.md"])[0]
            clean_rel = rel_path.replace("\\", "/").strip("/")

            self.engine.log(f"📥 [GET] Peer {self.client_address[0]} solicitou: {clean_rel}")

            if clean_rel == "shared_notes.md":
                target_file = self.engine.global_notes_file
            else:
                target_file = self.engine.project_notes_dir / Path(clean_rel).name

            if target_file.exists():
                body = target_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.engine.log(f"📤 [SERVINDO] {clean_rel} enviado para {self.client_address[0]} ({len(body)} bytes).")
            else:
                self.engine.log(f"⚠️ [GET] Arquivo não encontrado: {clean_rel}")
                self.send_error(404, "Arquivo não encontrado")
        else:
            self.send_error(404)

    def do_POST(self):
        """Mantém compatibilidade com push direto (caso o firewall permita no futuro)."""
        if self.path != "/sync":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_error(400, "Corpo vazio")
                return

            body = self.rfile.read(content_length)
            received_hmac = self.headers.get("X-Mesh-HMAC", "")
            note_rel_path = self.headers.get("X-Mesh-Path", "shared_notes.md").strip()
            clean_rel = note_rel_path.replace("\\", "/").strip("/")

            if ".." in clean_rel or clean_rel.startswith("/"):
                self.engine.log(f"🚨 [SEGURANÇA] Bloqueada tentativa de Path Traversal: {note_rel_path}")
                self.send_error(403, "Caminho proibido")
                return

            computed_hmac = hmac.new(self.engine.secret_key, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(received_hmac, computed_hmac):
                self.send_error(401, "HMAC Invalido")
                return

            new_hash = hashlib.sha256(body).hexdigest()

            if clean_rel == "shared_notes.md":
                self.engine.global_notes_file.write_bytes(body)
                self.engine._file_mtimes[str(self.engine.global_notes_file)] = self.engine.global_notes_file.stat().st_mtime
                self.engine._file_network_hashes["shared_notes.md"] = new_hash
            else:
                target_dest = self.engine.project_notes_dir / Path(clean_rel).name
                target_dest.parent.mkdir(parents=True, exist_ok=True)
                target_dest.write_bytes(body)
                self.engine._file_mtimes[str(target_dest)] = target_dest.stat().st_mtime
                self.engine._file_network_hashes[clean_rel] = new_hash

            self.engine.last_sync_time = time.time()
            self.engine.peer_ip = self.client_address[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

            self.engine.log(f"📥 [RECEBIDO] {clean_rel} sincronizado de {self.client_address[0]} ({len(body)} bytes).")
            self.engine._update_state_file("connected")

        except Exception as e:
            self.engine.log(f"✖ Erro no processamento do sync HTTP: {e}")
            self.send_error(500)


class NoteMeshEngine:
    """Nó P2P soberano em modo PULL-ONLY (Zero-Firewall-Dependency)."""

    def __init__(self, password: Optional[str] = None):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.doxoade_dir.mkdir(parents=True, exist_ok=True)

        self.global_notes_file = self.doxoade_dir / "shared_notes.md"
        self.project_root = self._resolve_real_project_root()
        self.project_notes_file = self.project_root / "shared_notes.md"
        self.project_notes_dir = self.project_root / ".doxoade" / "note"
        self.project_notes_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.doxoade_dir / "mesh_state.json"
        self.key_file = self.doxoade_dir / "mesh_auth.key"
        self.pid_file = self.doxoade_dir / "mesh_daemon.pid"
        self.log_file = self.doxoade_dir / "mesh.log"

        if not self.global_notes_file.exists():
            self.global_notes_file.write_text("# DoxNote Shared\n", encoding="utf-8")

        self.secret_key = self._load_or_create_key(password)
        self.hostname = socket.gethostname()
        self.local_ip = self._get_local_ip()
        self.running = False

        cached_peer = self._load_cached_peer()
        self.peer_ip: Optional[str] = cached_peer.get("ip")
        self.peer_name: Optional[str] = cached_peer.get("name")
        self.last_sync_time: float = 0.0

        self._file_mtimes: Dict[str, float] = {}
        self._file_sent_hashes: Dict[str, str] = {}
        self._file_network_hashes: Dict[str, str] = {}

        self._init_catalog_state()

        self.log("=" * 60)
        self.log("🌐 DOXNOTE MESH v5.0 — PULL-ONLY MODE ATIVO")
        self.log("=" * 60)
        self.log(f"  Modo         : PULL-ONLY (Zero-Firewall-Dependency)")
        self.log(f"  Global Notes : {self.global_notes_file}")
        self.log(f"  Project Notes: {self.project_notes_dir}/*.md")
        self.log(f"  Peer IP      : {self.peer_ip or 'Aguardando descoberta...'}")
        self.log("=" * 60)

    def _resolve_real_project_root(self) -> Path:
        """Localiza a pasta raiz real do projeto em desenvolvimento."""
        last_proj = self.doxoade_dir / "last_project.txt"
        if last_proj.exists():
            try:
                line = last_proj.read_text(encoding="utf-8").strip().splitlines()[0]
                p = Path(line).resolve()
                if p.exists() and not str(p).lower().endswith(".config"):
                    return p
            except Exception:
                pass

        try:
            from doxoade.tools.filesystem import _find_project_root
            found = _find_project_root(os.getcwd())
            p_found = Path(found).resolve()
            if not str(p_found).lower().endswith(".config"):
                return p_found
        except Exception:
            pass

        return Path.cwd().resolve()

    @property
    def notes_file(self) -> Path:
        """Alias de compatibilidade retroativa."""
        return self.global_notes_file

    def _init_catalog_state(self):
        """Inicializa carimbos e hashes de todas as notas monitoradas."""
        for p in [self.global_notes_file, self.project_notes_file]:
            if p.exists():
                m = p.stat().st_mtime
                h = self._calculate_file_hash(p)
                self._file_mtimes[str(p)] = m
                self._file_sent_hashes[p.name] = h
                self._file_network_hashes[p.name] = h

        if self.project_notes_dir.exists():
            for p in self.project_notes_dir.glob("*.md"):
                if not p.name.startswith("."):
                    m = p.stat().st_mtime
                    h = self._calculate_file_hash(p)
                    self._file_mtimes[str(p)] = m
                    rel = f"note/{p.name}"
                    self._file_sent_hashes[rel] = h
                    self._file_network_hashes[rel] = h

    @classmethod
    def is_service_running(cls) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            res = s.connect_ex(("127.0.0.1", TCP_PORT))
            s.close()
            return res == 0
        except Exception:
            return False

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _load_or_create_key(self, password: Optional[str]) -> bytes:
        if password:
            key = hashlib.sha256(password.encode("utf-8")).digest()
            self.key_file.write_bytes(key)
            return key

        if self.key_file.exists() and self.key_file.stat().st_size == 32:
            return self.key_file.read_bytes()

        default_key = hashlib.sha256(b"doxoade_sovereign_mesh_key").digest()
        self.key_file.write_bytes(default_key)
        return default_key

    def _calculate_file_hash(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _get_current_notes_hash(self) -> str:
        """Calcula o hash combinado de todas as notas monitoradas."""
        combined = ""
        if self.global_notes_file.exists():
            combined += self.global_notes_file.read_text(encoding="utf-8", errors="replace")

        if self.project_notes_dir.exists():
            for p in sorted(self.project_notes_dir.glob("*.md")):
                if not p.name.startswith("."):
                    combined += p.read_text(encoding="utf-8", errors="replace")

        return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

    def _load_cached_peer(self) -> dict:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                pip = data.get("peer_ip")
                if pip and pip != "Nenhum" and pip != self.local_ip:
                    return {"ip": pip, "name": data.get("peer_name")}
            except Exception:
                pass
        return {}

    def _update_state_file(self, status: str):
        state = {
            "status": status,
            "pid": os.getpid(),
            "hostname": self.hostname,
            "local_ip": self.local_ip,
            "peer_name": self.peer_name or "Nenhum",
            "peer_ip": self.peer_ip or "Nenhum",
            "last_sync": time.strftime("%H:%M:%S", time.localtime(self.last_sync_time)) if self.last_sync_time else "Nunca",
            "updated_at": time.time()
        }
        try:
            self.state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _beacon_loop(self):
        """Loop de descoberta UDP com anúncio de hash das notas."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", UDP_PORT))
        sock.settimeout(1.0)

        self.log(f"📡 [BEACON] Escutando na porta UDP {UDP_PORT}...")

        last_bcast = 0.0
        last_notes_hash = ""

        while self.running:
            now = time.time()

            # Anunciar a cada 3 segundos
            if now - last_bcast >= 3.0:
                current_hash = self._get_current_notes_hash()

                # Só anunciar se o hash mudou ou a cada 15s
                if current_hash != last_notes_hash or now - last_bcast >= 15.0:
                    manifest = {
                        "magic": MESH_MAGIC,
                        "hostname": self.hostname,
                        "ip": self.local_ip,
                        "port": TCP_PORT,
                        "notes_hash": current_hash,
                        "timestamp": now
                    }
                    try:
                        data = json.dumps(manifest).encode("utf-8")
                        parts = self.local_ip.split(".")
                        subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                        sock.sendto(data, (subnet_bcast, UDP_PORT))
                        sock.sendto(data, ("255.255.255.255", UDP_PORT))

                        if current_hash != last_notes_hash:
                            self.log(f"📢 [BEACON] Anunciando hash atualizado: {current_hash[:8]}...")
                            last_notes_hash = current_hash

                        last_bcast = now
                    except Exception as e:
                        self.log(f"⚠️ [BEACON] Falha ao anunciar: {e}")

            # Receber beacons de outros peers
            try:
                data, addr = sock.recvfrom(4096)
                if addr[0] == self.local_ip:
                    continue

                try:
                    manifest = json.loads(data.decode("utf-8"))
                    if manifest.get("magic") == MESH_MAGIC:
                        peer_ip = manifest.get("ip")
                        peer_name = manifest.get("hostname", "Unknown")
                        peer_hash = manifest.get("notes_hash", "")

                        if peer_ip and peer_ip != self.local_ip:
                            self.peer_ip = peer_ip
                            self.peer_name = peer_name
                            self._update_state_file("connected")

                            # 🔄 AUTO-PULL: Se o hash do peer é diferente, puxar
                            if peer_hash:
                                local_hash = self._file_sent_hashes.get("shared_notes.md", "")
                                if peer_hash != local_hash:
                                    self.log(f"🔄 [AUTO-PULL] Detectada alteração no peer {peer_name} ({peer_ip}). Puxando...")
                                    threading.Thread(
                                        target=self._fetch_from_peer,
                                        args=(peer_ip, TCP_PORT, "shared_notes.md"),
                                        daemon=True
                                    ).start()

                except Exception as e:
                    pass

            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"⚠️ [BEACON] Erro inesperado: {e}")

        sock.close()

    def _fetch_from_peer(self, peer_ip: str, peer_port: int, rel_path: str):
        """Busca automaticamente o arquivo do peer (Auto-Pull)."""
        url = f"http://{peer_ip}:{peer_port}/sync?fetch={quote(rel_path)}"
        self.log(f"📥 [FETCH] Tentando puxar {rel_path} de {peer_ip}:{peer_port}...")

        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    body = resp.read()

                    if rel_path == "shared_notes.md":
                        self.global_notes_file.write_bytes(body)
                        self._file_mtimes[str(self.global_notes_file)] = self.global_notes_file.stat().st_mtime
                        self._file_sent_hashes["shared_notes.md"] = hashlib.sha256(body).hexdigest()
                    else:
                        target_dest = self.project_notes_dir / Path(rel_path).name
                        target_dest.parent.mkdir(parents=True, exist_ok=True)
                        target_dest.write_bytes(body)
                        self._file_mtimes[str(target_dest)] = target_dest.stat().st_mtime
                        self._file_sent_hashes[f"note/{Path(rel_path).name}"] = hashlib.sha256(body).hexdigest()

                    self.last_sync_time = time.time()
                    self.log(f"✅ [AUTO-PULL OK] {rel_path} atualizado de {peer_ip} ({len(body)} bytes).")
                    self._update_state_file("connected")
        except Exception as e:
            self.log(f"⚠️ [AUTO-PULL FALHA] Não foi possível puxar de {peer_ip}: {e}")

    def _http_server_loop(self):
        """Servidor HTTP para atender requisições GET (Auto-Pull) e POST."""
        MeshSyncHTTPHandler.engine = self
        server = HTTPServer(("0.0.0.0", TCP_PORT), MeshSyncHTTPHandler)
        server.timeout = 1.0

        self.log(f"🌐 [HTTP] Servidor escutando na porta TCP {TCP_PORT}...")

        while self.running:
            server.handle_request()

        server.server_close()

    def _file_watcher_loop(self):
        """Monitora alterações nos arquivos e anuncia via Beacon (NÃO faz push direto)."""
        while self.running:
            time.sleep(0.3)

            watch_targets = [self.global_notes_file]
            if self.project_notes_file != self.global_notes_file and self.project_notes_file.exists():
                watch_targets.append(self.project_notes_file)

            if self.project_notes_dir.exists():
                for p in self.project_notes_dir.glob("*.md"):
                    if not p.name.startswith("."):
                        watch_targets.append(p)

            for path in watch_targets:
                if not path.exists():
                    continue

                current_mtime = path.stat().st_mtime
                last_mtime = self._file_mtimes.get(str(path), 0)

                if current_mtime > last_mtime:
                    self._file_mtimes[str(path)] = current_mtime
                    current_hash = self._calculate_file_hash(path)
                    rel = path.name if path == self.global_notes_file else f"note/{path.name}"

                    if current_hash != self._file_sent_hashes.get(rel, ""):
                        self._file_sent_hashes[rel] = current_hash
                        self.log(f"📝 [DETECTADO] Alteração em {rel}. Anunciando via Beacon...")
                        # O Beacon loop vai anunciar automaticamente no próximo ciclo

    def start(self):
        """Inicia todos os threads do motor P2P."""
        if self.running:
            return

        self.running = True

        # Testar se a porta TCP está disponível
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(0.5)
        try:
            test_sock.bind(("0.0.0.0", TCP_PORT))
            test_sock.close()
        except OSError as e:
            self.log(f"🚨 [CRÍTICO] Porta TCP {TCP_PORT} já está em uso! Encerrando...")
            self.running = False
            return

        self.pid_file.write_text(str(os.getpid()), encoding="utf-8")

        threads = [
            threading.Thread(target=self._beacon_loop, daemon=True),
            threading.Thread(target=self._http_server_loop, daemon=True),
            threading.Thread(target=self._file_watcher_loop, daemon=True),
        ]

        for t in threads:
            t.start()

        self.log("✔ [MESH] Todos os threads iniciados com sucesso.")

    def stop(self):
        """Para todos os threads e limpa recursos."""
        self.running = False
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception:
            pass
        self.log("🛑 [MESH] Serviço encerrado.")
