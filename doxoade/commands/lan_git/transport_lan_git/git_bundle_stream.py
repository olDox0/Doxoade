# doxoade/commands/lan_git/transport_lan_git/git_bundle_stream.py
# Plano C: Exportador e transmissor de .bundle raw
""" Módulo de Transmissão de Git Bundle com Validação SHA-256 (Plano C - Fallback).
Empacota branches/commits em arquivo binário autocontido e transmite via socket autenticado. """

import os
import socket
import hashlib
import struct
import tempfile
import subprocess
from typing import Optional, Tuple


BUNDLE_MAGIC = b"DOX_BUNDLE_V1"


class GitBundleHost:
    """Gera e envia o arquivo .bundle através de socket seguro."""

    @staticmethod
    def create_bundle(repo_path: str, output_bundle_path: str, branch: str = "HEAD") -> bool:
        try:
            res = subprocess.run(
                ["git", "-C", repo_path, "bundle", "create", output_bundle_path, branch],
                capture_output=True,
                timeout=30,
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def serve_bundle(cls, repo_path: str, port: int = 54546, token: str = "") -> Tuple[bool, Optional[str]]:
        """Cria bundle temporário e aguarda a conexão de 1 cliente autorizado."""
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as tmp:
            tmp_bundle = tmp.name

        try:
            if not cls.create_bundle(repo_path, tmp_bundle):
                return False, "Falha ao gerar o Git Bundle local."

            with open(tmp_bundle, "rb") as f:
                bundle_data = f.read()

            sha256_hash = hashlib.sha256(bundle_data).digest()
            data_len = len(bundle_data)

            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(("0.0.0.0", port))
            server_sock.listen(1)
            server_sock.settimeout(60.0)  # Aguarda até 60s pelo cliente

            client_sock, _ = server_sock.accept()
            
            # Envia Cabeçalho: MAGIC (13B) + TAMANHO (8B uint64) + SHA256 (32B)
            header = BUNDLE_MAGIC + struct.pack("!Q", data_len) + sha256_hash
            client_sock.sendall(header)
            client_sock.sendall(bundle_data)

            client_sock.close()
            server_sock.close()
            return True, None
        except Exception as e:
            return False, f"Falha no streaming do bundle: {e}"
        finally:
            if os.path.exists(tmp_bundle):
                try:
                    os.remove(tmp_bundle)
                except Exception:
                    pass


class GitBundleClient:
    """Recebe o stream binário, valida o hash SHA-256 e salva o bundle local."""

    @staticmethod
    def receive_bundle(host_ip: str, port: int = 54546, output_path: str = "received.bundle") -> Tuple[bool, Optional[str]]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15.0)
            sock.connect((host_ip, port))

            # Lê cabeçalho (13B magic + 8B length + 32B sha256 = 53 bytes)
            header_size = len(BUNDLE_MAGIC) + 8 + 32
            header = sock.recv(header_size)
            if len(header) < header_size or not header.startswith(BUNDLE_MAGIC):
                sock.close()
                return False, "Cabeçalho de Bundle inválido ou rejeitado."

            magic_len = len(BUNDLE_MAGIC)
            expected_len = struct.unpack("!Q", header[magic_len:magic_len+8])[0]
            expected_sha = header[magic_len+8:magic_len+8+32]

            # Recebe o payload do bundle
            received_data = bytearray()
            while len(received_data) < expected_len:
                chunk = sock.recv(min(65536, expected_len - len(received_data)))
                if not chunk:
                    break
                received_data.extend(chunk)

            sock.close()

            if len(received_data) != expected_len:
                return False, "Transferência corrompida: tamanho incompatível."

            calculated_sha = hashlib.sha256(received_data).digest()
            if calculated_sha != expected_sha:
                return False, "Alerta de Segurança: Falha na integridade do hash SHA-256 do Bundle."

            with open(output_path, "wb") as f:
                f.write(received_data)

            return True, None
        except Exception as e:
            return False, f"Falha na recepção do Bundle: {e}"