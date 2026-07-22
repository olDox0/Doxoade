# doxoade/tools/hermes_systems/async_echo.py
import ctypes
import os
import sys
import time
import atexit
import subprocess

class _AsyncEchoCore:
    """
    Núcleo de I/O Assíncrono (Hermes Ring Buffer SPSC).
    Substitui o print() tradicional em loops críticos para evitar bloqueio de GIL e Syscalls.
    """
    DEBUG, INFO, WARN, ERROR = 0, 1, 2, 3
    _COLORS = {0: "\033[90m", 1: "\033[32m", 2: "\033[33m", 3: "\033[31m"}
    _RST = "\033[0m"

    def __init__(self):
        self.lib = None
        self._initialized = False
        self._ensure_compiled() # 🛡️ LAZY BUILD (Metalcraft sob demanda)
        self._load_bridge()
        atexit.register(self.shutdown)

    def _ensure_compiled(self):
        """Se a DLL/SO não existir, invoca o GCC do Metalcraft para forjá-la."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        native_dir = os.path.join(base_dir, 'native')
        os.makedirs(native_dir, exist_ok=True)
        
        lib_name = 'hermes_async_log.dll' if sys.platform == 'win32' else 'hermes_async_log.so'
        lib_path = os.path.join(native_dir, lib_name)
        src_path = os.path.join(native_dir, 'hermes_async_log.c')
        
        if os.path.exists(lib_path) or not os.path.exists(src_path):
            return

        try:
            # Usa a NexusToolchain do Metalcraft para achar o GCC
            from doxoade.tools.metalcraft.metal_toolchain import NexusToolchain
            tc = NexusToolchain()
            if not tc.detect():
                return # Sem GCC, fallback para print síncrono
                
            print(f"\033[90m[HERMES] Forjando Bridge Assíncrona ({lib_name})...\033[0m")
            
            cmd = [tc.compiler_path, "-O3", "-Wall"]
            if sys.platform == 'win32':
                cmd += ["-shared", "-o", lib_path, src_path]
            else:
                cmd += ["-shared", "-fPIC", "-o", lib_path, src_path, "-lpthread"]
                
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except Exception:
            pass # Fallback silencioso

    def _load_bridge(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        native_dir = os.path.join(base_dir, 'native')
        lib_name = 'hermes_async_log.dll' if sys.platform == 'win32' else 'hermes_async_log.so'
        lib_path = os.path.join(native_dir, lib_name)
            
        if not os.path.exists(lib_path):
            return

        try:
            self.lib = ctypes.CDLL(lib_path)
            self.lib.hermes_log_py_init.argtypes = []
            self.lib.hermes_log_py_init.restype = None
            self.lib.hermes_log_py_shutdown.argtypes = []
            self.lib.hermes_log_py_shutdown.restype = None
            self.lib.hermes_log_py_push.argtypes = [ctypes.c_char_p, ctypes.c_uint8]
            self.lib.hermes_log_py_push.restype = None
            
            self.lib.hermes_log_py_init()
            self._initialized = True
        except Exception:
            self.lib = None

    def push(self, message: str, level: int = 1):
        if self.lib and self._initialized:
            # O ctypes libera o GIL automaticamente aqui!
            self.lib.hermes_log_py_push(message.encode('utf-8'), level)
        else:
            # Fallback Síncrono (Caso não haja GCC ou a DLL falhe)
            prefix = ["DBG", "INF", "WRN", "ERR"][level]
            color = self._COLORS[level]
            print(f"{color}[{prefix}]{self._RST} {message}")

    def shutdown(self):
        if self.lib and self._initialized:
            self.lib.hermes_log_py_shutdown()
            self._initialized = False

# Instância Global (Singleton)
_echo_core = _AsyncEchoCore()

# ═══════════════════════════════════════════════════════════════════
# API PÚBLICA (Drop-in replacement para print)
# ═══════════════════════════════════════════════════════════════════
def echout(*args, sep=' ', end='\n', level='auto'):
    """
    Print Assíncrono de Alta Performance (Zero-Config).
    Uso: echout("Processando", var1, var2)
    """
    msg = sep.join(str(a) for a in args)
    if end: msg += end
    
    lvl_int = 1 # Default INFO
    if level == 'auto':
        lower_msg = msg.lower()
        if any(w in lower_msg for w in ['error', 'fail', 'crash', 'erro', 'falha', 'exceção']):
            lvl_int = 3
        elif any(w in lower_msg for w in ['warn', 'aviso', 'cuidado', 'atenção']):
            lvl_int = 2
        elif any(w in lower_msg for w in ['debug', 'trace', 'dbg']):
            lvl_int = 0
            
    _echo_core.push(msg, lvl_int)