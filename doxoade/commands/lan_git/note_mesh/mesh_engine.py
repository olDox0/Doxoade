# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_engine.py
"""
🌐 DOXNOTE MESH ENGINE v3.0 — Dual-Watchdog & Resilient Unicast Peering.
Monitora tanto ~/.doxoade/shared_notes.md quanto ./shared_notes.md.
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
from typing import Optional, Dict, Any, List

MESH_MAGIC = "DOX_MESH_V3"
UDP_PORT = 54547
TCP_PORT = 54548


class NoteMeshEngine:
    """Nó P2P soberano com Dual-Watchdog e Peering Resiliente."""

    def __init__(self, password: Optional[str] = None):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.doxoade_dir.mkdir(parents=True, exist_ok=True)
        
        # 📂 Arquivo canônico global
        self.global_notes_file = self.doxoade_dir / "shared_notes.md"
        # 📂 Arquivo local do projeto (se existir)
        self.project_notes_file = Path.cwd() / "shared_notes.md"
        
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

        # Recupera último peer conhecido do cache
        cached_peer = self._load_cached_peer()
        self.peer_ip: Optional[str] = cached_peer.get("ip")
        self.peer_name: Optional[str] = cached_peer.get("name")
        self.last_sync_time: float = 0.0

        self._last_sent_hash: str = self._calculate_file_hash(self.global_notes_file)
        self._last_network_hash: str = self._last_sent_hash
        self._last_global_mtime: float = self.global_notes_file.stat().st_mtime
        self._last_proj_mtime: float = self.project_notes_file.stat().st_mtime if self.project_notes_file.exists() else 0.0

    @classmethod
    def is_service_running(cls) -> bool:
        """Verifica de forma atômica se o serviço já está ativo na porta TCP 54548."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            res = s.connect_ex(("127.0.0.1", TCP_PORT))
            s.close()
            return res == 0
        except Exception:
            return False
            
    def log(self, msg: str):
        """Grava log com timestamp legível para telemetria forense."""
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
        """Descoberta contínua em broadcast local e direto na sub-rede."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("0.0.0.0", UDP_PORT))
        except Exception:
            return
        sock.setblocking(False)

        # Calcula o broadcast da sub-rede local (ex: 192.168.18.255)
        subnet_bcast = "255.255.255.255"
        if self.local_ip.startswith("192.168."):
            parts = self.local_ip.split(".")
            subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"

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

                # Se já temos um peer salvo em cache, envia probe unicast direto
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

    def _tcp_server_loop(self):
        """Servidor de recepção atômica de notas (Push-Receiver)."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", TCP_PORT))
        except OSError:
            self.log(f"⚠ Porta {TCP_PORT} já em uso. Daemon anterior ativo.")
            sys.exit(0)

        server.listen(5)
        server.settimeout(1.0)

        while self.running:
            try:
                client_sock, addr = server.accept()
                threading.Thread(target=self._handle_incoming_push, args=(client_sock, addr[0]), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break
        server.close()

    def _handle_incoming_push(self, sock: socket.socket, sender_ip: str):
        """Recebe payload da rede, valida HMAC e atualiza ambos os arquivos."""
        try:
            sock.settimeout(4.0)
            raw_header = sock.recv(32 + 8 + 4)
            if len(raw_header) < 44:
                sock.close()
                return

            expected_hmac = raw_header[:32]
            ts_bytes = raw_header[32:40]
            len_bytes = raw_header[40:44]
            data_len = int.from_bytes(len_bytes, "big")

            body = bytearray()
            while len(body) < data_len:
                chunk = sock.recv(min(8192, data_len - len(body)))
                if not chunk:
                    break
                body.extend(chunk)

            computed_hmac = hmac.new(self.secret_key, ts_bytes + len_bytes + body, hashlib.sha256).digest()
            if not hmac.compare_digest(expected_hmac, computed_hmac):
                sock.close()
                return

            new_hash = hashlib.sha256(body).hexdigest()
            self._last_network_hash = new_hash

            # Atualiza o arquivo global
            self.global_notes_file.write_bytes(body)
            self._last_global_mtime = self.global_notes_file.stat().st_mtime

            # Se o projeto tiver seu próprio shared_notes.md, sincroniza ele também!
            if self.project_notes_file.exists():
                try:
                    self.project_notes_file.write_bytes(body)
                    self._last_proj_mtime = self.project_notes_file.stat().st_mtime
                except Exception:
                    pass

            self.last_sync_time = time.time()
            self.peer_ip = sender_ip
            sock.sendall(b"OK")
            self.log(f"📥 [RECEBIDO] Nota sincronizada de {sender_ip} ({len(body)} bytes).")
            self._update_state_file("connected")
        except Exception as e:
            self.log(f"✖ Erro ao receber push: {e}")
        finally:
            sock.close()

    def send_push_to_peer(self, content_bytes: bytes) -> bool:
        """Envia atualização atômica para o par com tolerância a oscilação de Wi-Fi."""
        target_ip = self.peer_ip
        if not target_ip:
            self.log("⚠️ Nenhum IP de par detectado para envio.")
            return False

        # Tenta até 2 vezes se o Wi-Fi der pico de latência
        for tentativa in range(1, 3):
            t0 = time.perf_counter()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Timeout generoso de 7s para não quebrar em oscilações
                sock.settimeout(7.0)
                sock.connect((target_ip, TCP_PORT))

                ts_bytes = int(time.time()).to_bytes(8, "big")
                len_bytes = len(content_bytes).to_bytes(4, "big")
                token_hmac = hmac.new(self.secret_key, ts_bytes + len_bytes + content_bytes, hashlib.sha256).digest()

                sock.sendall(token_hmac + ts_bytes + len_bytes + content_bytes)
                ack = sock.recv(2)
                sock.close()

                if ack == b"OK":
                    rtt = (time.perf_counter() - t0) * 1000.0
                    self.last_sync_time = time.time()
                    self.log(f"📤 [ENVIADO] {len(content_bytes)} bytes entregues a {target_ip} em {rtt:.1f}ms! ✔")
                    self._update_state_file("connected")
                    return True
            except Exception as e:
                if tentativa == 1:
                    time.sleep(0.2)  # Pausa rápida antes do retry
                else:
                    self.log(f"✖ Falha no envio para {target_ip}: {e}")
        return False

    def _file_watcher_loop(self):
        """Dual-Watchdog veloz (300ms): Detecta o salvamento quase instantaneamente!"""
        while self.running:
            time.sleep(0.3)  # 👈 Reduzido de 1.0s para 0.3s
            target_to_sync = None

            if self.global_notes_file.exists():
                try:
                    m = self.global_notes_file.stat().st_mtime
                    if m > self._last_global_mtime:
                        self._last_global_mtime = m
                        target_to_sync = self.global_notes_file
                except Exception:
                    pass

            if self.project_notes_file.exists():
                try:
                    m = self.project_notes_file.stat().st_mtime
                    if m > self._last_proj_mtime:
                        self._last_proj_mtime = m
                        target_to_sync = self.project_notes_file
                except Exception:
                    pass

            if target_to_sync:
                try:
                    content = target_to_sync.read_bytes()
                    cur_hash = hashlib.sha256(content).hexdigest()

                    if cur_hash != self._last_network_hash and cur_hash != self._last_sent_hash:
                        self.log(f"📝 [SALVAMENTO DETECTADO] em: {target_to_sync.name}")
                        if self.send_push_to_peer(content):
                            self._last_sent_hash = cur_hash
                            if target_to_sync == self.global_notes_file and self.project_notes_file.exists():
                                self.project_notes_file.write_bytes(content)
                                self._last_proj_mtime = self.project_notes_file.stat().st_mtime
                            elif target_to_sync == self.project_notes_file:
                                self.global_notes_file.write_bytes(content)
                                self._last_global_mtime = self.global_notes_file.stat().st_mtime
                except Exception as e:
                    self.log(f"✖ Erro no watchdog: {e}")

    def start(self):
        self.running = True
        try:
            self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

        threading.Thread(target=self._beacon_loop, daemon=True).start()
        threading.Thread(target=self._tcp_server_loop, daemon=True).start()
        threading.Thread(target=self._file_watcher_loop, daemon=True).start()

        self.log(f"============================================================")
        self.log(f"       DOXNOTE MESH v3.0 — DUAL-WATCHDOG ATIVO")
        self.log(f"============================================================")
        self.log(f"  Home Notes    : {self.global_notes_file}")
        self.log(f"  Project Notes : {self.project_notes_file if self.project_notes_file.exists() else '(não criado no projeto)'}")
        self.log(f"  Peer IP       : {self.peer_ip or 'Aguardando Descoberta...'}")
        self.log(f"============================================================")

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
