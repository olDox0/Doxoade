# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_engine.py
"""
🌐 DOXNOTE MESH ENGINE v4.0 — Multi-Note Directory Watcher & HTTP REST Transport.
Sincroniza tanto shared_notes.md quanto múltiplos cadernos em .doxoade/note/*.md.
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
from typing import Optional, Dict, Any, List

from doxoade.commands.lan_git.note_mesh.mesh_firewall_guard import MeshFirewallGuard
from doxoade.commands.lan_git.note_mesh.mesh_debug_logger import MeshDebugLogger


MESH_MAGIC = "DOX_MESH_V4"
UDP_PORT = 54547
TCP_PORT = 54548


class MeshSyncHTTPHandler(BaseHTTPRequestHandler):
    """Handler HTTP atômico com suporte a múltiplos arquivos de notas."""
    engine: NoteMeshEngine = None

    def log_message(self, format, *args):
        pass  # Silencia logs automáticos de console

    def do_POST(self):
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

            # 🛡️ ANÚBIS SHIELD: Proteção contra Path Traversal
            clean_rel = note_rel_path.replace("\\", "/").strip("/")
            if ".." in clean_rel or clean_rel.startswith("/"):
                self.engine.log(f"🚨 [SEGURANÇA] Bloqueada tentativa de Path Traversal: {note_rel_path}")
                self.send_error(403, "Caminho proibido")
                return

            # Valida HMAC com a chave compartilhada da malha
            computed_hmac = hmac.new(self.engine.secret_key, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(received_hmac, computed_hmac):
                self.send_error(401, "HMAC Invalido")
                return

            new_hash = hashlib.sha256(body).hexdigest()

            # 📂 Roteamento e Destino
            if clean_rel == "shared_notes.md":
                self.engine.global_notes_file.write_bytes(body)
                self.engine._file_mtimes[str(self.engine.global_notes_file)] = self.engine.global_notes_file.stat().st_mtime
                if self.engine.project_notes_file.exists():
                    try:
                        self.engine.project_notes_file.write_bytes(body)
                        self.engine._file_mtimes[str(self.engine.project_notes_file)] = self.engine.project_notes_file.stat().st_mtime
                    except Exception:
                        pass
                self.engine._file_network_hashes["shared_notes.md"] = new_hash
            else:
                # Salva notas do projeto em .doxoade/note/ na raiz real
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
    """Nó P2P soberano com suporte a diretório multi-notas."""

    def __init__(self, password: Optional[str] = None):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.doxoade_dir.mkdir(parents=True, exist_ok=True)

        self.global_notes_file = self.doxoade_dir / "shared_notes.md"
        
        # 📂 2. Raiz Real do Projeto (Resolve de last_project.txt ou busca recursiva)
        self.project_root = self._resolve_real_project_root()
        self.project_notes_file = self.project_root / "shared_notes.md"
        self.project_notes_dir = self.project_root / ".doxoade" / "note"
        self.project_notes_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.doxoade_dir / "mesh_state.json"
        self.key_file = self.doxoade_dir / "mesh_auth.key"
        self.pid_file = self.doxoade_dir / "mesh_daemon.pid"
        self.log_file = self.doxoade_dir / "mesh.log"

        if not self.global_notes_file.exists():
            self.global_notes_file.write_text("# 📝 Doxoade Shared Notes\n\n", encoding="utf-8")

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

        self.debug = MeshDebugLogger()
        self.fw_guard = MeshFirewallGuard()

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
        """Alias de compatibilidade retroativa para cli_lan_git."""
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
            "updated_at": time.time(),
        }
        try:
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _beacon_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("0.0.0.0", UDP_PORT))
        except Exception:
            return
        sock.setblocking(False)

        subnet_bcast = "255.255.255.255"
        if self.local_ip.startswith("192.168."):
            parts = self.local_ip.split(".")
            subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"

        if not self.peer_ip:
            from doxoade.commands.lan_git.discovery_lan_git.scanner_lan_git import LANDirectScanner
            # Tentar IPs conhecidos da sub-rede
            for candidate_ip in self._get_subnet_candidates():
                try:
                    resp = self._probe_peer(candidate_ip)
                    if resp:
                        self.peer_ip = candidate_ip
                        self.peer_name = resp.get("hostname", "Unknown")
                        self._update_state_file("connected")
                        self.log(f"🔍 [DISCOVERY] Peer encontrado via probe: {candidate_ip}")
                        break
                except Exception:
                    continue

        last_bcast = 0.0
        while self.running:
            now = time.time()
            if now - last_bcast > 3.0:
                payload = json.dumps({
                    "magic": MESH_MAGIC,
                    "host": self.hostname,
                    "ip": self.local_ip,
                    "tcp_port": TCP_PORT
                }).encode("utf-8")

                for target_ip in [subnet_bcast, "255.255.255.255"]:
                    try:
                        sock.sendto(payload, (target_ip, UDP_PORT))
                    except Exception:
                        pass

                if self.peer_ip:
                    try:
                        sock.sendto(payload, (self.peer_ip, UDP_PORT))
                    except Exception:
                        pass

                last_bcast = now
                self._update_state_file("connected" if self.peer_ip else "searching")

            ready = select.select([sock], [], [], 0.5)
            if ready[0]:
                try:
                    data, addr = sock.recvfrom(2048)
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("magic") == MESH_MAGIC and msg.get("ip") != self.local_ip:
                        if self.peer_ip != msg["ip"]:
                            self.peer_ip = msg["ip"]
                            self.peer_name = msg.get("host")
                            self.log(f"📡 [DESCOBERTA] Par conectado: {self.peer_name} ({self.peer_ip})")
                except Exception:
                    pass
        sock.close()

    def _http_server_loop(self):
        MeshSyncHTTPHandler.engine = self
        try:
            server = HTTPServer(("0.0.0.0", TCP_PORT), MeshSyncHTTPHandler)
            server.timeout = 1.0
        except OSError:
            self.log(f"⚠ Porta {TCP_PORT} já em uso.")
            sys.exit(0)

        while self.running:
            server.handle_request()
        server.server_close()

    def send_push_to_peer(self, file_path: Path, rel_path: str):
        if not self.peer_ip:
            self.debug.event("SEND", "Sem peer descoberto", rel_path=rel_path)
            self.log("⚠ [MESH] Nenhum peer descoberto. Aguardando beacon...")
            return

        self.debug.counter("sends_attempted")
        url = f"http://{self.peer_ip}:{TCP_PORT}/sync"
        body = file_path.read_bytes()
        mac = hmac.new(self.secret_key, body, hashlib.sha256).hexdigest()

        req = Request(url, data=body, method="POST")
        req.add_header("X-Mesh-HMAC", mac)
        req.add_header("X-Mesh-Path", rel_path)

        try:
            t0 = time.time()
            with urlopen(req, timeout=5) as resp:
                elapsed = (time.time() - t0) * 1000
                self.debug.counter("sends_ok")
                self.debug.event("SEND", "Push entregue", rel_path=rel_path, peer=self.peer_ip, latency_ms=round(elapsed, 2), bytes=len(body))
                self.log(f"📤 [ENVIADO] {rel_path} ({len(body)} bytes) → {self.peer_ip} em {elapsed:.1f}ms ✔")
        except TimeoutError:
            self.debug.counter("sends_failed")
            self.debug.counter("timeouts")
            self.debug.event("SEND", "TIMEOUT no push", rel_path=rel_path, peer=self.peer_ip, bytes=len(body))
            self.log(f"✖ Falha: {self.peer_ip}:{TCP_PORT} inacessível (TIMEOUT).")

            # ─── AUTO-DIAGNÓSTICO E CORREÇÃO ─────────────────────
            self.log("🔍 [GUARD] Executando diagnóstico automático de firewall...")
            report = self.fw_guard.run_full_diagnostic(self.peer_ip)
            self.debug.event("GUARD", "Diagnóstico completo", **report)

            if report["verdict"] == "OUTBOUND_BLOCKED":
                self.log("🛡️ [GUARD] Solicitando permissão de firewall (UAC)...")
                perm_result = self.fw_guard.request_firewall_permission(ttl_hours=24)
                self.debug.event("GUARD", "Solicitação de permissão", **perm_result)

                if perm_result.get("rules_created"):
                    self.log(f"✅ [GUARD] Regras criadas! Expiram em: {perm_result.get('expire_at')}")
                elif perm_result.get("uac_result") == "user_denied":
                    self.log("⚠️ [GUARD] Usuário recusou a elevação. Sincronização permanecerá bloqueada.")
                else:
                    self.log(f"❌ [GUARD] Falha: {perm_result.get('errors')}")
            else:
                self.log("✅ [GUARD] Conectividade OK. O problema pode ser no servidor de destino.")

        except Exception as e:
            self.debug.counter("sends_failed")
            self.debug.event("SEND", "Erro no push", rel_path=rel_path, error=str(e))
            self.log(f"✖ Falha no envio de {rel_path}: {e}")

    def _file_watcher_loop(self):
        """Dual-Watchdog Multi-Note: Vigia shared_notes E todos os .doxoade/note/*.md."""
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
                        self.send_push_to_peer(path, rel)

    def start(self):
        self.running = True
        try:
            self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

        threading.Thread(target=self._beacon_loop, daemon=True).start()
        threading.Thread(target=self._http_server_loop, daemon=True).start()
        threading.Thread(target=self._file_watcher_loop, daemon=True).start()

        self.log("============================================================")
        self.log("    DOXNOTE MESH v4.0 — MULTI-NOTE MESH TRANSPORT ATIVO")
        self.log("============================================================")
        self.log(f"  Global Notes  : {self.global_notes_file}")
        self.log(f"  Project Notes : {self.project_notes_dir}/*.md")
        self.log(f"  Peer IP       : {self.peer_ip or 'Aguardando Descoberta...'}")
        self.log("============================================================")

        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        self._update_state_file("offline")
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception:
            pass
