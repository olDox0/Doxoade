# -*- coding: utf-8 -*-
# doxoade/tools/terminal_systems/__init__.py
"""
🖥️ DOXOADE TERMINAL SYSTEMS — Subsistema de Terminal Interativo e Streaming PTY.
Exporta o Daemon de Sessão Persistente e Gerenciador de I/O.
Compliance: ProDeNov 1.2.1, PASC-6.1.
"""

from .terminal_stream_daemon import TerminalStreamDaemon, TerminalSessionConfig

__all__ = ["TerminalStreamDaemon", "TerminalSessionConfig"]
