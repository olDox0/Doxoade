# doxoade\tools\async_log_systems\__init__.py
"""
Async Log Systems - I/O Não-Bloqueante via Ring Buffer SPSC (PASC 13.0)
Substitui print() tradicional em loops críticos.
"""
from .async_echo import echout, debug, info, warn, error, drain

__all__ = ['echout', 'debug', 'info', 'warn', 'error', 'drain']