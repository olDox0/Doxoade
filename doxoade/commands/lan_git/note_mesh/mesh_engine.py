# doxoade/commands/lan_git/note_mesh/mesh_engine.py
"""
🌐 DOXNOTE MESH ENGINE — Motor P2P Simétrico para Sincronização de Notas.
Opera nas portas dedicadas 54547/UDP (Beacon) e 54548/TCP (Sync Seguro).
Implementa:
  • Pareamento por chave compartilhada (HMAC-SHA256).
  • Imunidade contra loops de eco (Anti-Echo Hash Filter).
  • Despejo de estado para a IDE (~/.doxoade/mesh_state.json).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""


import click
import hashlib
import hmac
import json
import os
import select
import socket
import sys
import threading
import time

from pathlib import Path
from typing import Optional, Tuple, Dict, Any

MESH_MAGIC = "DOX_MESH_V1"
UDP_PORT = 54547
TCP_PORT = 54548


class NoteMeshEngine:
    """Nó P2P autônomo para sincronização de notas entre máquinas na LAN."""

    def __init__(self, password: Optional[str] = None):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.doxoade_dir.mkdir(parents=True, exist_ok=True)

        self.notes_file = self.doxoade_dir / "shared_notes.md"
        self.state_file = self.doxoade_dir / "mesh_state.json"
        self.key_file = self.doxoade_dir / "mesh_auth.key"

        if not self.notes_file.exists():
            self.notes_file.write_text("# 📝 Notas Compartilhadas DoxNote\n\n", encoding="utf-8")

        self.secret_key = self._load_or_create_key(password)
        self.hostname = socket.gethostname()
        self.local_ip = self._get_local_ip()

        self.running = False
        self.connected_peer_ip: Optional[str] = None
        self.connected_peer_name: Optional[str] = None
        self.last_sync_time: float = 0.0
        self.last_rtt_ms: float = 0.0

        # Filtro Anti-Echo
        self._last_processed_hash: str = self._calculate_file_hash()
        self._last_mtime: float = self.notes_file.stat().st_mtime

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
        # Chave padrão da malha LAN
        default_key = hashlib.sha256(b"doxoade_sovereign_mesh_key").digest()
        self.key_file.write_bytes(default_key)
        return default_key

    def _calculate_file_hash(self) -> str:
        if not self.notes_file.exists():
            return ""
        try:
            return hashlib.sha256(self.notes_file.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _update_state_file(self, status: str):
        state = {
            "status": status,
            "pid": os.getpid(),
            "hostname": self.hostname,
            "local_ip": self.local_ip,
            "peer_name": self.connected_peer_name or "Nenhum",
            "peer_ip": self.connected_peer_ip or "Nenhum",
            "last_sync": time.strftime("%H:%M:%S", time.localtime(self.last_sync_time)) if self.last_sync_time else "Nunca",
            "rtt_ms": round(self.last_rtt_ms, 2),
            "updated_at": time.time()
        }
        try:
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════
    # CAMADA 1: BEACON UDP (DESCOBERTA MÚTUA NA PORTA 54547)
    # ═════════════════════════════════════════════════════════════════
    def _beacon_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", UDP_PORT))
        sock.setblocking(False)

        last_broadcast = 0.0
        while self.running:
            now = time.time()
            # Envia ping de anúncio a cada 3 segundos se não estiver conectado
            if now - last_broadcast > 3.0:
                payload = json.dumps({
                    "magic": MESH_MAGIC,
                    "host": self.hostname,
                    "ip": self.local_ip,
                    "tcp_port": TCP_PORT
                }).encode("utf-8")
                try:
                    sock.sendto(payload, ("255.255.255.255", UDP_PORT))
                except Exception:
                    pass
                last_broadcast = now

            # Escuta anúncios de outros computadores
            ready = select.select([sock], [], [], 0.5)
            if ready[0]:
                try:
                    data, addr = sock.recvfrom(2048)
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("magic") == MESH_MAGIC and msg.get("ip") != self.local_ip:
                        remote_ip = msg["ip"]
                        if not self.connected_peer_ip:
                            self.connected_peer_name = msg.get("host")
                            # Conecta via TCP ao par descoberto
                            threading.Thread(target=self._connect_to_peer, args=(remote_ip,), daemon=True).start()
                except Exception:
                    pass
        sock.close()

    # ═════════════════════════════════════════════════════════════════
    # CAMADA 2: TRANSPORTE TCP & HANDSHAKE (PORTA 54548)
    # ═════════════════════════════════════════════════════════════════
    def _tcp_server_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", TCP_PORT))
        server.listen(2)
        server.settimeout(1.0)

        while self.running:
            try:
                client_sock, addr = server.accept()
                peer_ip = addr[0]
                if peer_ip != self.local_ip:
                    threading.Thread(target=self._handle_client_socket, args=(client_sock, peer_ip), daemon=True).start()
                else:
                    client_sock.close()
            except socket.timeout:
                continue
            except Exception:
                break
        server.close()

    def _handle_client_socket(self, sock: socket.socket, peer_ip: str):
        sock.settimeout(10.0)
        try:
            # 1. Handshake de Autenticação HMAC
            challenge = os.urandom(16)
            sock.sendall(challenge)
            expected_hmac = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()

            received_hmac = sock.recv(32)
            if not hmac.compare_digest(expected_hmac, received_hmac):
                sock.close()
                return

            sock.sendall(b"OK")
            self.connected_peer_ip = peer_ip
            self._update_state_file("connected")

            # 2. Loop de Recepção de Dados
            while self.running:
                raw_len = sock.recv(4)
                if not raw_len or len(raw_len) < 4:
                    break
                data_len = int.from_bytes(raw_len, "big")
                payload_bytes = bytearray()
                while len(payload_bytes) < data_len:
                    chunk = sock.recv(min(8192, data_len - len(payload_bytes)))
                    if not chunk:
                        break
                    payload_bytes.extend(chunk)

                if len(payload_bytes) == data_len:
                    self._apply_incoming_sync(payload_bytes)
        except Exception:
            pass
        finally:
            sock.close()
            if self.connected_peer_ip == peer_ip:
                self.connected_peer_ip = None
                self._update_state_file("searching")

    def _connect_to_peer(self, peer_ip: str):
        if self.connected_peer_ip:
            return
        t0 = time.perf_counter_ns()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((peer_ip, TCP_PORT))

            challenge = sock.recv(16)
            if len(challenge) != 16:
                sock.close()
                return

            response_hmac = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()
            sock.sendall(response_hmac)

            auth_res = sock.recv(2)
            if auth_res == b"OK":
                self.connected_peer_ip = peer_ip
                self.last_rtt_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
                self._update_state_file("connected")

                # Transmite o estado local inicial
                self._send_file_to_socket(sock)

                # Mantém socket ouvindo
                while self.running and self.connected_peer_ip == peer_ip:
                    time.sleep(1.0)
            sock.close()
        except Exception:
            pass
        finally:
            if self.connected_peer_ip == peer_ip:
                self.connected_peer_ip = None
                self._update_state_file("searching")

    def _send_file_to_socket(self, sock: socket.socket):
        try:
            content = self.notes_file.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()
            payload = json.dumps({
                "hash": content_hash,
                "ts": time.time(),
                "content": content.decode("utf-8", errors="replace")
            }).encode("utf-8")

            length_header = len(payload).to_bytes(4, "big")
            sock.sendall(length_header + payload)
            self._last_processed_hash = content_hash
        except Exception:
            pass

    def _apply_incoming_sync(self, raw_data: bytes):
        try:
            msg = json.loads(raw_data.decode("utf-8"))
            in_hash = msg.get("hash")
            in_content = msg.get("content")

            # 🛡️ FILTRO ANTI-ECHO: Se o hash for igual ao que já temos, descarta!
            if in_hash and in_hash == self._last_processed_hash:
                return

            self.notes_file.write_text(in_content, encoding="utf-8")
            self._last_processed_hash = in_hash
            self._last_mtime = self.notes_file.stat().st_mtime
            self.last_sync_time = time.time()
            self._update_state_file("connected")
            click.secho(f"  [{time.strftime('%H:%M:%S')}] ⚡ [SYNC RECEBIDO] Notas atualizadas via DoxNote Mesh.", fg="green")
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════
    # CAMADA 3: WATCHER LOCAL (DETECÇÃO DE SALVAMENTO NA IDE)
    # ═════════════════════════════════════════════════════════════════
    def _file_watcher_loop(self):
        last_heartbeat = 0.0
        while self.running:
            time.sleep(0.35)
            now = time.time()
            
            # 💓 Heartbeat a cada 2s para avisar a IDE que o daemon está vivo
            if now - last_heartbeat > 2.0:
                current_status = "connected" if self.connected_peer_ip else "searching"
                self._update_state_file(current_status)
                last_heartbeat = now

            if not self.notes_file.exists():
                continue
            try:
                curr_mtime = self.notes_file.stat().st_mtime
                if curr_mtime != self._last_mtime:
                    self._last_mtime = curr_mtime
                    curr_hash = self._calculate_file_hash()
                    
                    if curr_hash != self._last_processed_hash:
                        self._last_processed_hash = curr_hash
                        self.last_sync_time = time.time()
                        if self.connected_peer_ip:
                            threading.Thread(target=self._broadcast_change, args=(self.connected_peer_ip,), daemon=True).start()
                            click.secho(f"  [{time.strftime('%H:%M:%S')}] 📤 [SYNC] Transmitido para {self.connected_peer_ip}.", fg="cyan")
            except Exception:
                pass

    def _broadcast_change(self, peer_ip: str):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((peer_ip, TCP_PORT))
            challenge = sock.recv(16)
            response_hmac = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()
            sock.sendall(response_hmac)
            if sock.recv(2) == b"OK":
                self._send_file_to_socket(sock)
            sock.close()
        except Exception:
            pass

    def start(self):
        """Inicia todas as threads da malha."""
        self.running = True
        self._update_state_file("searching")
        
        threading.Thread(target=self._beacon_loop, daemon=True).start()
        threading.Thread(target=self._tcp_server_loop, daemon=True).start()
        threading.Thread(target=self._file_watcher_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self._update_state_file("offline")
