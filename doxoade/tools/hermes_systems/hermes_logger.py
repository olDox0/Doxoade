#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_logger.py
"""
Hermes Async Logger - Python Wrapper
=====================================
Interface Python para o Async Logger em C.
Usa ctypes para chamar as funções da DLL/SO.

Uso:
    from doxoade.tools.hermes_systems.hermes_logger import HermesLogger
    
    logger = HermesLogger()
    logger.info("Mensagem de informação")
    logger.warn("Aviso importante")
    logger.error("Erro crítico")
    logger.debug("Debug detalhado")
    
    # Estatísticas
    stats = logger.get_stats()
    print(f"Logs processados: {stats['total']}")
"""
import os
import sys
import json
import ctypes
from pathlib import Path
from typing import Dict, Optional
from enum import IntEnum

class LogLevel(IntEnum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3

class HermesLogger:
    """Wrapper Python para o Async Logger em C."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if HermesLogger._initialized:
            return
        
        self._lib = None
        self._load_library()
        HermesLogger._initialized = True
    
    def _load_library(self):
        """Carrega a DLL/SO do logger."""
        native_dir = Path(__file__).parent / 'native'
        
        if os.name == 'nt':
            lib_name = 'hermes_async_log.dll'
        else:
            lib_name = 'hermes_async_log.so'
        
        lib_path = native_dir / lib_name
        
        if not lib_path.exists():
            print(f"[HERMES-LOGGER] ⚠ Biblioteca não encontrada: {lib_path}")
            print(f"[HERMES-LOGGER] ⚠ Compile com: doxoade hermes build-logger")
            return
        
        try:
            self._lib = ctypes.CDLL(str(lib_path))
            
            # Configura protótipos das funções
            self._lib.hermes_log_py_init.argtypes = []
            self._lib.hermes_log_py_init.restype = None
            
            self._lib.hermes_log_py_shutdown.argtypes = []
            self._lib.hermes_log_py_shutdown.restype = None
            
            self._lib.hermes_log_py_push.argtypes = [ctypes.c_char_p, ctypes.c_uint8]
            self._lib.hermes_log_py_push.restype = None
            
            self._lib.hermes_log_py_get_stats.argtypes = []
            self._lib.hermes_log_py_get_stats.restype = ctypes.c_char_p
            
            # Inicializa o logger
            self._lib.hermes_log_py_init()
            print(f"[HERMES-LOGGER] ✔ Logger assíncrono inicializado")
            
        except Exception as e:
            print(f"[HERMES-LOGGER] ✘ Falha ao carregar biblioteca: {e}")
            self._lib = None
    
    def debug(self, message: str):
        """Log de debug."""
        self._push(message, LogLevel.DEBUG)
    
    def info(self, message: str):
        """Log de informação."""
        self._push(message, LogLevel.INFO)
    
    def warn(self, message: str):
        """Log de aviso."""
        self._push(message, LogLevel.WARN)
    
    def error(self, message: str):
        """Log de erro."""
        self._push(message, LogLevel.ERROR)
    
    def _push(self, message: str, level: LogLevel):
        """Envia uma mensagem para o logger."""
        if not self._lib:
            # Fallback: print direto
            level_name = level.name
            print(f"[{level_name}] {message}")
            return
        
        try:
            self._lib.hermes_log_py_push(message.encode('utf-8'), level.value)
        except Exception as e:
            print(f"[HERMES-LOGGER] ✘ Erro ao enviar log: {e}")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do logger."""
        if not self._lib:
            return {'total': 0, 'dropped': 0, 'elapsed_ms': 0}
        
        try:
            stats_json = self._lib.hermes_log_py_get_stats().decode('utf-8')
            return json.loads(stats_json)
        except Exception as e:
            print(f"[HERMES-LOGGER] ✘ Erro ao obter estatísticas: {e}")
            return {'total': 0, 'dropped': 0, 'elapsed_ms': 0}
    
    def shutdown(self):
        """Desliga o logger."""
        if self._lib:
            self._lib.hermes_log_py_shutdown()
            print(f"[HERMES-LOGGER] ✔ Logger desligado")

# ═══════════════════════════════════════════════════════════════════
# INSTÂNCIA GLOBAL (Singleton)
# ═══════════════════════════════════════════════════════════════════
_logger_instance: Optional[HermesLogger] = None

def get_logger() -> HermesLogger:
    """Retorna a instância global do logger."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = HermesLogger()
    return _logger_instance

# Atalhos de conveniência
def debug(msg: str): get_logger().debug(msg)
def info(msg: str): get_logger().info(msg)
def warn(msg: str): get_logger().warn(msg)
def error(msg: str): get_logger().error(msg)