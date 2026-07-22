# doxoade\tools\async_log_systems\async_echo.py
"""
Wrapper Python para Async Logger C (Lazy Build + API print-like).
"""
import ctypes
import os
import sys
import atexit
import subprocess

class _AsyncEchoCore:
    """Núcleo de I/O Assíncrono com Lazy Build via Metalcraft."""
    DEBUG, INFO, WARN, ERROR = 0, 1, 2, 3
    _COLORS = {0: "\033[90m", 1: "\033[32m", 2: "\033[33m", 3: "\033[31m"}
    _RST = "\033[0m"

    def __init__(self):
        self.lib = None
        self._initialized = False
        self._ensure_compiled()  # 🛡️ LAZY BUILD
        self._load_bridge()
        atexit.register(self.shutdown)

    def _ensure_compiled(self):
        """Se a DLL/SO não existir, invoca o Metalcraft para forjá-la."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        native_dir = os.path.join(base_dir, 'native')
        os.makedirs(native_dir, exist_ok=True)
        
        lib_name = 'async_log.dll' if sys.platform == 'win32' else 'async_log.so'
        lib_path = os.path.join(native_dir, lib_name)
        src_path = os.path.join(native_dir, 'async_log.c')
        hdr_path = os.path.join(native_dir, 'async_log.h')
        
        if os.path.exists(lib_path) or not os.path.exists(src_path):
            return

        try:
            from doxoade.tools.metalcraft.metal_toolchain import NexusToolchain
            tc = NexusToolchain()
            if not tc.detect():
                return
                
            print(f"\033[90m[ASYNC-LOG] Forjando Bridge ({lib_name})...\033[0m")
            
            cmd = [tc.compiler_path, "-O3", "-Wall", "-Wno-unused-function"]
            if sys.platform == 'win32':
                cmd += ["-shared", f"-I{native_dir}", "-o", lib_path, src_path]
            else:
                cmd += ["-shared", "-fPIC", f"-I{native_dir}", "-o", lib_path, src_path, "-lpthread"]
                
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"\033[31m[ASYNC-LOG] Build falhou: {res.stderr[:200]}\033[0m")
        except Exception as e:
            pass

    def _load_bridge(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        native_dir = os.path.join(base_dir, 'native')
        lib_name = 'async_log.dll' if sys.platform == 'win32' else 'async_log.so'
        lib_path = os.path.join(native_dir, lib_name)
            
        if not os.path.exists(lib_path):
            return

        try:
            self.lib = ctypes.CDLL(lib_path)
            self.lib.async_log_init.argtypes = []
            self.lib.async_log_init.restype = None
            self.lib.async_log_shutdown.argtypes = []
            self.lib.async_log_shutdown.restype = None
            self.lib.async_log_push.argtypes = [ctypes.c_char_p, ctypes.c_uint8]
            self.lib.async_log_push.restype = None
            
            self.lib.async_log_init()
            self._initialized = True

            self.lib.async_log_drain.argtypes = []
            self.lib.async_log_drain.restype = None
        except Exception:
            self.lib = None

    def drain(self):
        """Espera a thread C terminar de imprimir todos os logs do buffer."""
        if self.lib and self._initialized:
            self.lib.async_log_drain()

    def push(self, message: str, level: int = 1):
        if self.lib and self._initialized:
            self.lib.async_log_push(message.encode('utf-8'), level)
        else:
            prefix = ["DBG", "INF", "WRN", "ERR"][level]
            color = self._COLORS[level]
            print(f"{color}[{prefix}]{self._RST} {message}")

    def shutdown(self):
        if self.lib and self._initialized:
            self.lib.async_log_shutdown()
            self._initialized = False

# Singleton Global
_echo_core = _AsyncEchoCore()

# ═══════════════════════════════════════════════════════════════════
# API PÚBLICA (Drop-in replacement para print)
# ═══════════════════════════════════════════════════════════════════
def echout(*args, sep=' ', end='\n', level='auto'):
    """Print Assíncrono de Alta Performance (Zero-Config)."""
    msg = sep.join(str(a) for a in args)
    if end: msg += end
    
    lvl_int = 1
    if level == 'auto':
        lower_msg = msg.lower()
        if any(w in lower_msg for w in ['error', 'fail', 'crash', 'erro', 'falha', 'exceção']):
            lvl_int = 3
        elif any(w in lower_msg for w in ['warn', 'aviso', 'cuidado', 'atenção']):
            lvl_int = 2
        elif any(w in lower_msg for w in ['debug', 'trace', 'dbg']):
            lvl_int = 0
            
    _echo_core.push(msg, lvl_int)

def debug(msg): echout(msg, "debug")
def info(msg):  echout(msg, "info")
def warn(msg):  echout(msg, "warn")
def error(msg): echout(msg, "error")
def drain():
    """Drena o buffer assíncrono. Use antes de imprimir relatórios finais."""
    _echo_core.drain()