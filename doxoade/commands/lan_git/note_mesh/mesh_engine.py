# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_engine.py
"""
🌐 DOXNOTE MESH ENGINE v2.0 — Motor P2P Simétrico e Atômico (Push on Change).
Sem sockets persistentes bloqueantes: Transmissão atômica com ACK imediato.
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
from typing import Optional, Dict, Any

MESH_MAGIC = "DOX_MESH_V2"
UDP_PORT = 54547
TCP_PORT = 54548


class NoteMeshEngine:
    """Nó P2P soberano com sincronização simétrica atômica."""

    def __init__(self, password: Optional[str] = None):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.doxoade_dir.mkdir(parents=True, exist_ok=True)
        self.notes_file = self.doxoade_dir / "shared_notes.md"
        self.state_file = self.doxoade_dir / "mesh_state.json"
        self.key_file = self.doxoade_dir / "mesh_auth.key"
        self.pid_file = self.doxoade_dir / "mesh_daemon.pid"

        if not self.notes_file.exists():
            self.notes_file.write_text("# 📝 Doxoade Shared Notes\n\n", encoding="utf-8")

        self.secret_key = self._load_or_create_key(password)
        self.hostname = socket.gethostname()
        self.local_ip = self._get_local_ip()
        self.running = False

        self.peer_ip: Optional[str] = None
        self.peer_name: Optional[str] = None
        self.last_sync_time: float = 0.0
        self.last_rtt_ms: float = 0.0

        self._last_sent_hash: str = self._calculate_file_hash()
        self._last_network_hash: str = self._last_sent_hash
        self._last_mtime: float = self.notes_file.stat().st_mtime

    @classmethod
    def is_service_running(cls) -> bool:
        """Verifica de forma atômica se o serviço já está ouvindo na porta TCP 54548."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            res = s.connect_ex(("127.0.0.1", TCP_PORT))
            s.close()
            return res == 0
        except Exception:
            return False

    def _enforce_single_instance(self):
        """Trava atômica no bind da porta (imune a PIDs reciclados no Windows)."""
        lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            lock_sock.bind(("127.0.0.1", TCP_PORT))
            lock_sock.close()
        except OSError:
            # Se a porta já está ocupada, sai silenciosamente sem erro
            sys.exit(0)
            
        try:
            self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def ensure_background_running(cls, password: Optional[str] = None) -> bool:
        """Garante que o serviço esteja rodando em background; se não estiver, sobe silenciosamente."""
        if cls.is_service_running():
            return True
        import subprocess
        cmd = [sys.executable, "-m", "doxoade", "lan-git", "note", "service", "-d"]
        if password:
            cmd.extend(["--password", password])
        
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | 0x00000008  # DETACHED_PROCESS
            
        try:
            subprocess.Popen(cmd, creationflags=flags, close_fds=True)
            return True
        except Exception:
            return False

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
            "peer_name": self.peer_name or "Nenhum",
            "peer_ip": self.peer_ip or "Nenhum",
            "last_sync": time.strftime("%H:%M:%S", time.localtime(self.last_sync_time)) if self.last_sync_time else "Nunca",
            "rtt_ms": round(self.last_rtt_ms, 2),
            "updated_at": time.time(),
        }
        try:
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _beacon_loop(self):
        """Descoberta contínua via UDP Broadcast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("0.0.0.0", UDP_PORT))
        except Exception:
            return
        sock.setblocking(False)

        last_broadcast = 0.0
        while self.running:
            now = time.time()
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
                self._update_state_file("connected" if self.peer_ip else "searching")

            ready = select.select([sock], [], [], 0.5)
            if ready[0]:
                try:
                    data, addr = sock.recvfrom(2048)
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("magic") == MESH_MAGIC and msg.get("ip") != self.local_ip:
                        self.peer_ip = msg["ip"]
                        self.peer_name = msg.get("host")
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
            print(f"⚠ [DOXNOTE MESH] Porta {TCP_PORT} já em uso. Encerrando duplicata.")
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
        """Recebe payload com autenticação HMAC, salva no disco e responde OK."""
        try:
            sock.settimeout(4.0)
            raw_header = sock.recv(32 + 8 + 4)  # HMAC (32) + Timestamp (8) + Len (4)
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

            # Valida autenticação
            computed_hmac = hmac.new(self.secret_key, ts_bytes + len_bytes + body, hashlib.sha256).digest()
            if not hmac.compare_digest(expected_hmac, computed_hmac):
                sock.close()
                return

            # Grava no arquivo
            new_hash = hashlib.sha256(body).hexdigest()
            self._last_network_hash = new_hash
            self.notes_file.write_bytes(body)
            self._last_mtime = self.notes_file.stat().st_mtime
            self.last_sync_time = time.time()

            # Responde ACK
            sock.sendall(b"OK")
            self.peer_ip = sender_ip
            self._update_state_file("connected")
        except Exception:
            pass
        finally:
            sock.close()

    def send_push_to_peer(self, content_bytes: bytes) -> bool:
        """Envia atualização atômica para o par na rede."""
        if not self.peer_ip:
            return False
        t0 = time.perf_counter_ns()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((self.peer_ip, TCP_PORT))

            ts_bytes = int(time.time()).to_bytes(8, "big")
            len_bytes = len(content_bytes).to_bytes(4, "big")
            token_hmac = hmac.new(self.secret_key, ts_bytes + len_bytes + content_bytes, hashlib.sha256).digest()

            header = token_hmac + ts_bytes + len_bytes
            sock.sendall(header + content_bytes)

            ack = sock.recv(2)
            sock.close()

            if ack == b"OK":
                self.last_rtt_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
                self.last_sync_time = time.time()
                self._update_state_file("connected")
                return True
        except Exception:
            pass
        return False

    def _file_watcher_loop(self):
        """Monitora modificações locais no arquivo e dispara envio imediato."""
        while self.running:
            time.sleep(1.0)
            if not self.notes_file.exists():
                continue
            try:
                cur_mtime = self.notes_file.stat().st_mtime
                if cur_mtime > self._last_mtime:
                    self._last_mtime = cur_mtime
                    content = self.notes_file.read_bytes()
                    cur_hash = hashlib.sha256(content).hexdigest()

                    # Só envia se foi alterado LOCALMENTE (não eco da rede)
                    if cur_hash != self._last_network_hash and cur_hash != self._last_sent_hash:
                        if self.send_push_to_peer(content):
                            self._last_sent_hash = cur_hash
            except Exception:
                pass

    def start(self):
        self.running = True
        try:
            self.pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

        t_beacon = threading.Thread(target=self._beacon_loop, daemon=True)
        t_server = threading.Thread(target=self._tcp_server_loop, daemon=True)
        t_watcher = threading.Thread(target=self._file_watcher_loop, daemon=True)

        t_beacon.start()
        t_server.start()
        t_watcher.start()

        print("============================================================")
        print("          DOXNOTE MESH — SERVIÇO P2P DE NOTAS ATIVO")
        print("============================================================")
        print(f"  Arquivo Global : {self.notes_file}")
        print(f"  Porta Beacon   : {UDP_PORT}/UDP (Descoberta P2P)")
        print(f"  Porta Sync     : {TCP_PORT}/TCP (Push Atômico)")
        print(f"  Dispositivo    : {self.hostname} ({self.local_ip})")
        print("============================================================")
        print("📡 Malha P2P Ativa. Sincronizando com a IDE em tempo real...\n")

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
