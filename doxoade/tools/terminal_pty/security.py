# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/security.py
"""
🔒 Segurança do Socket PTY — Token HMAC, Validação e Timeout.

Blindagens implementadas:
  • Bind APENAS em 127.0.0.1 (nunca 0.0.0.0)
  • Token HMAC-SHA256 aleatório por sessão (32 bytes)
  • Token expira em 30s se o cliente não autenticar
  • Máximo 1 conexão simultânea
  • SO_REUSEADDR desativado (evita port hijack)

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import socket
import time
from dataclasses import dataclass, field
from typing import Optional

# Configurações de segurança
BIND_HOST = "127.0.0.1"
PORT_RANGE_START = 19840
PORT_RANGE_END = 19899
AUTH_TIMEOUT_SECONDS = 30.0
TOKEN_LENGTH_BYTES = 32
MAX_CONCURRENT_CONNECTIONS = 1


@dataclass
class SessionToken:
    """Token de sessão com metadados de expiração."""
    token: str
    created_at: float
    expires_at: float
    is_used: bool = False

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_used


class PTYSecurityManager:
    """Gerencia tokens de sessão e validação de conexões."""

    def __init__(self):
        self._current_token: Optional[SessionToken] = None
        self._secret_key: bytes = secrets.token_bytes(32)

    def generate_token(self) -> str:
        """
        Gera um novo token HMAC-SHA256 para a sessão.
        O token é válido por AUTH_TIMEOUT_SECONDS.
        """
        raw_token = secrets.token_bytes(TOKEN_LENGTH_BYTES)
        timestamp = time.time()

        # HMAC-SHA259: token = HMAC(secret, raw + timestamp)
        payload = raw_token + str(timestamp).encode("utf-8")
        signature = hmac.new(
            self._secret_key, payload, hashlib.sha256
        ).hexdigest()

        # Formato: hex(raw):timestamp:signature
        token_str = f"{raw_token.hex()}:{timestamp}:{signature}"

        self._current_token = SessionToken(
            token=token_str,
            created_at=timestamp,
            expires_at=timestamp + AUTH_TIMEOUT_SECONDS,
        )

        return token_str

    def validate_token(self, received_token: str) -> bool:
        """
        Valida o token recebido contra o token ativo.
        Usa comparação em tempo constante para evitar timing attacks.
        """
        if self._current_token is None:
            return False

        if not self._current_token.is_valid:
            return False

        # Comparação em tempo constante
        is_match = hmac.compare_digest(
            received_token.encode("utf-8"),
            self._current_token.token.encode("utf-8"),
        )

        if is_match:
            self._current_token.is_used = True

        return is_match

    def invalidate_token(self) -> None:
        """Invalida o token atual (após uso ou timeout)."""
        if self._current_token is not None:
            self._current_token.is_used = True
            self._current_token = None

    @property
    def active_token(self) -> Optional[SessionToken]:
        return self._current_token

    @property
    def has_valid_token(self) -> bool:
        return self._current_token is not None and self._current_token.is_valid


def find_available_port() -> int:
    """
    Encontra uma porta disponível no range definido.
    Faz bind temporário para verificar disponibilidade.
    """
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            sock.bind((BIND_HOST, port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError(
        f"Nenhuma porta disponível no range {PORT_RANGE_START}-{PORT_RANGE_END}"
    )


def create_secure_socket(port: int) -> socket.socket:
    """
    Cria um socket TCP seguro com bind apenas em localhost.
    SO_REUSEADDR desativado para evitar port hijack.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.bind((BIND_HOST, port))
    sock.listen(MAX_CONCURRENT_CONNECTIONS)
    sock.settimeout(AUTH_TIMEOUT_SECONDS)
    return sock


def format_ready_line(
    port: int,
    token: str,
    shell: str,
    pid: int,
    conpty_available: bool = True,
) -> str:
    """
    Formata a linha de handshake que o Python imprime no stdout
    para o Lite XL parsear.

    Formato: DOX_PTY_READY|port=<N>|token=<T>|shell=<S>|pid=<P>|conpty=<0|1>
    """
    conpty_flag = "1" if conpty_available else "0"
    return (
        f"DOX_PTY_READY"
        f"|port={port}"
        f"|token={token}"
        f"|shell={shell}"
        f"|pid={pid}"
        f"|conpty={conpty_flag}"
    )


def parse_ready_line(line: str) -> Optional[dict]:
    """
    Parseia a linha DOX_PTY_READY retornada pelo Python.
    Usado pelo lado Lua/cliente.

    Retorna dict com: port, token, shell, pid, conpty
    """
    if not line.startswith("DOX_PTY_READY|"):
        return None

    result = {}
    try:
        payload = line.split("|", 1)[1]
        for part in payload.split("|"):
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()

        result["port"] = int(result["port"])
        result["pid"] = int(result["pid"])
        result["conpty"] = result.get("conpty", "1") == "1"
    except (ValueError, IndexError, KeyError):
        return None

    return result


__all__ = [
    "BIND_HOST",
    "PORT_RANGE_START",
    "PORT_RANGE_END",
    "AUTH_TIMEOUT_SECONDS",
    "SessionToken",
    "PTYSecurityManager",
    "find_available_port",
    "create_secure_socket",
    "format_ready_line",
    "parse_ready_line",
]
