# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_protocol.py
"""
📡 Protocolo Binário de Comunicação Lua ↔ Python — Terminal PTY.

Formato de mensagem:
  [1 byte tipo][4 bytes payload length (big-endian)][payload UTF-8/binário]

Tipos Lua → Python:
  0x01 = INPUT_DATA     (teclas digitadas pelo usuário)
  0x02 = RESIZE         (cols: uint16, rows: uint16)
  0x03 = INTERRUPT      (Ctrl+C / SIGINT)
  0x04 = PING           (keepalive)
  0xFF = SHUTDOWN       (encerrar PTY e servidor)

Tipos Python → Lua:
  0x11 = OUTPUT_DATA    (bytes do stdout/stderr com ANSI)
  0x12 = PTY_EXITED     (código de saída: int32)
  0x13 = PONG           (resposta ao keepalive)
  0x14 = ERROR          (mensagem de erro UTF-8)
  0x15 = AUTH_OK        (autenticação bem-sucedida)
  0x16 = AUTH_FAIL      (autenticação falhou)

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple, Union


# ──────────────────────────────────────────────────────────────────────────────
# TIPOS DE MENSAGEM
# ──────────────────────────────────────────────────────────────────────────────

class MsgType(IntEnum):
    """Tipos de mensagem do protocolo PTY."""
    # Lua → Python
    INPUT_DATA = 0x01
    RESIZE = 0x02
    INTERRUPT = 0x03
    PING = 0x04
    SHUTDOWN = 0xFF

    # Python → Lua
    OUTPUT_DATA = 0x11
    PTY_EXITED = 0x12
    PONG = 0x13
    ERROR = 0x14
    AUTH_OK = 0x15
    AUTH_FAIL = 0x16


# Header: 1 byte tipo + 4 bytes length (big-endian)
HEADER_FORMAT = "!BI"  # network byte order (big-endian), unsigned char + unsigned int
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 5 bytes
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB max por mensagem


# ──────────────────────────────────────────────────────────────────────────────
# ESTRUTURAS DE MENSAGEM
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PTYMessage:
    """Mensagem genérica do protocolo PTY."""
    msg_type: MsgType
    payload: bytes = b""

    @property
    def payload_length(self) -> int:
        return len(self.payload)

    def to_bytes(self) -> bytes:
        """Serializa a mensagem para bytes (header + payload)."""
        header = struct.pack(HEADER_FORMAT, int(self.msg_type), self.payload_length)
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> Tuple[Optional["PTYMessage"], bytes]:
        """
        Desserializa uma mensagem a partir de um buffer de bytes.
        Retorna (mensagem, bytes_restantes) ou (None, buffer_original) se incompleto.
        """
        if len(data) < HEADER_SIZE:
            return None, data

        msg_type_raw, payload_length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])

        if payload_length > MAX_PAYLOAD_SIZE:
            raise ProtocolError(f"Payload excessivo: {payload_length} bytes")

        total_length = HEADER_SIZE + payload_length
        if len(data) < total_length:
            return None, data  # Mensagem incompleta, aguardar mais dados

        try:
            msg_type = MsgType(msg_type_raw)
        except ValueError:
            raise ProtocolError(f"Tipo de mensagem desconhecido: 0x{msg_type_raw:02X}")

        payload = data[HEADER_SIZE:total_length]
        remaining = data[total_length:]

        return cls(msg_type=msg_type, payload=payload), remaining


class ProtocolError(Exception):
    """Erro de protocolo de comunicação."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# CONSTRUTORES DE MENSAGEM (Python → Lua)
# ──────────────────────────────────────────────────────────────────────────────

def make_output_data(data: Union[str, bytes]) -> PTYMessage:
    """Cria mensagem de output do terminal (com ANSI)."""
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    return PTYMessage(msg_type=MsgType.OUTPUT_DATA, payload=data)


def make_pty_exited(exit_code: int) -> PTYMessage:
    """Cria mensagem indicando que o processo PTY terminou."""
    payload = struct.pack("!i", exit_code)  # int32 signed
    return PTYMessage(msg_type=MsgType.PTY_EXITED, payload=payload)


def make_pong() -> PTYMessage:
    """Cria resposta de keepalive."""
    return PTYMessage(msg_type=MsgType.PONG, payload=b"")


def make_error(message: str) -> PTYMessage:
    """Cria mensagem de erro."""
    payload = message.encode("utf-8", errors="replace")
    return PTYMessage(msg_type=MsgType.ERROR, payload=payload)


def make_auth_ok() -> PTYMessage:
    """Cria mensagem de autenticação bem-sucedida."""
    return PTYMessage(msg_type=MsgType.AUTH_OK, payload=b"OK")


def make_auth_fail(reason: str = "Token inválido ou expirado") -> PTYMessage:
    """Cria mensagem de falha de autenticação."""
    payload = reason.encode("utf-8", errors="replace")
    return PTYMessage(msg_type=MsgType.AUTH_FAIL, payload=payload)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTRUTORES DE MENSAGEM (Lua → Python)
# ──────────────────────────────────────────────────────────────────────────────

def make_input_data(text: Union[str, bytes]) -> PTYMessage:
    """Cria mensagem de input do teclado."""
    if isinstance(text, str):
        text = text.encode("utf-8", errors="replace")
    return PTYMessage(msg_type=MsgType.INPUT_DATA, payload=text)


def make_resize(cols: int, rows: int) -> PTYMessage:
    """Cria mensagem de resize do terminal."""
    payload = struct.pack("!HH", cols, rows)  # 2x uint16
    return PTYMessage(msg_type=MsgType.RESIZE, payload=payload)


def make_interrupt() -> PTYMessage:
    """Cria mensagem de interrupção (Ctrl+C)."""
    return PTYMessage(msg_type=MsgType.INTERRUPT, payload=b"")


def make_ping() -> PTYMessage:
    """Cria mensagem de keepalive."""
    return PTYMessage(msg_type=MsgType.PING, payload=b"")


def make_shutdown() -> PTYMessage:
    """Cria mensagem de encerramento."""
    return PTYMessage(msg_type=MsgType.SHUTDOWN, payload=b"")


# ──────────────────────────────────────────────────────────────────────────────
# PARSERS DE PAYLOAD
# ──────────────────────────────────────────────────────────────────────────────

def parse_input_data(msg: PTYMessage) -> bytes:
    """Extrai o payload de input como bytes."""
    return msg.payload


def parse_resize(msg: PTYMessage) -> Tuple[int, int]:
    """Extrai cols e rows de uma mensagem RESIZE."""
    if len(msg.payload) != 4:
        raise ProtocolError(f"RESIZE payload inválido: {len(msg.payload)} bytes")
    cols, rows = struct.unpack("!HH", msg.payload)
    return cols, rows


def parse_pty_exited(msg: PTYMessage) -> int:
    """Extrai o código de saída de PTY_EXITED."""
    if len(msg.payload) != 4:
        raise ProtocolError(f"PTY_EXITED payload inválido: {len(msg.payload)} bytes")
    exit_code = struct.unpack("!i", msg.payload)[0]
    return exit_code


def parse_error(msg: PTYMessage) -> str:
    """Extrai mensagem de erro como string."""
    return msg.payload.decode("utf-8", errors="replace")


def parse_output_data(msg: PTYMessage) -> bytes:
    """Extrai output do terminal como bytes (pode conter ANSI)."""
    return msg.payload


# ──────────────────────────────────────────────────────────────────────────────
# STREAM READER (Acumulador de buffer para mensagens fragmentadas)
# ──────────────────────────────────────────────────────────────────────────────

class ProtocolStreamReader:
    """
    Acumulador de buffer para leitura de mensagens fragmentadas.
    O socket TCP pode entregar dados em pedaços arbitrários.
    """

    def __init__(self):
        self._buffer: bytes = b""

    def feed(self, data: bytes) -> None:
        """Adiciona dados recebidos ao buffer interno."""
        self._buffer += data

    def read_message(self) -> Optional[PTYMessage]:
        """
        Tenta ler uma mensagem completa do buffer.
        Retorna None se ainda não houver mensagem completa.
        """
        if len(self._buffer) < HEADER_SIZE:
            return None

        try:
            msg, remaining = PTYMessage.from_bytes(self._buffer)
            if msg is not None:
                self._buffer = remaining
            return msg
        except ProtocolError:
            # Mensagem corrompida, descartar header e tentar recuperar
            self._buffer = self._buffer[1:]
            return None

    def read_all_messages(self) -> list:
        """Lê todas as mensagens completas disponíveis no buffer."""
        messages = []
        while True:
            msg = self.read_message()
            if msg is None:
                break
            messages.append(msg)
        return messages

    @property
    def pending_bytes(self) -> int:
        """Quantidade de bytes aguardando no buffer."""
        return len(self._buffer)

    def clear(self) -> None:
        """Limpa o buffer."""
        self._buffer = b""


# ──────────────────────────────────────────────────────────────────────────────
# AUTENTICAÇÃO (Fase de Handshake)
# ──────────────────────────────────────────────────────────────────────────────

AUTH_PREFIX = b"AUTH "
AUTH_RESPONSE_OK = b"AUTH_OK\n"
AUTH_RESPONSE_FAIL = b"AUTH_FAIL\n"


def build_auth_request(token: str) -> bytes:
    """Constrói a mensagem de autenticação inicial (antes do protocolo binário)."""
    return AUTH_PREFIX + token.encode("utf-8") + b"\n"


def parse_auth_request(data: bytes) -> Optional[str]:
    """
    Parseia a mensagem de autenticação inicial.
    Retorna o token ou None se não for uma mensagem AUTH válida.
    """
    if not data.startswith(AUTH_PREFIX):
        return None
    token_data = data[len(AUTH_PREFIX):]
    # Remove newline se presente
    if token_data.endswith(b"\n"):
        token_data = token_data[:-1]
    return token_data.decode("utf-8", errors="replace")


__all__ = [
    "MsgType",
    "PTYMessage",
    "ProtocolError",
    "ProtocolStreamReader",
    "HEADER_SIZE",
    "MAX_PAYLOAD_SIZE",
    # Construtores Python → Lua
    "make_output_data",
    "make_pty_exited",
    "make_pong",
    "make_error",
    "make_auth_ok",
    "make_auth_fail",
    # Construtores Lua → Python
    "make_input_data",
    "make_resize",
    "make_interrupt",
    "make_ping",
    "make_shutdown",
    # Parsers
    "parse_input_data",
    "parse_resize",
    "parse_pty_exited",
    "parse_error",
    "parse_output_data",
    # Auth
    "build_auth_request",
    "parse_auth_request",
]
