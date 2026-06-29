# doxoade/doxoade/tools/benzaiten_gui/benzaiten_core.py.py
import ctypes
import sys
import os
from pathlib import Path
from doxoade.tools.filesystem import _find_project_root

CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)

def _load_native_lib():
    """Localiza a DLL/SO compilada no projeto alvo."""
    root = Path(_find_project_root(os.getcwd()))
    bin_dir = root / ".doxoade" / "benzaiten"
    
    if sys.platform == 'win32':
        lib_path = bin_dir / 'dxgui.dll'
    elif sys.platform.startswith('linux'):
        lib_path = bin_dir / 'libdxgui.so'
    else:
        raise NotImplementedError("SO não suportado pelo Benzaiten.")
        
    if not lib_path.exists():
        raise FileNotFoundError(f"Motor Benzaiten não compilado. Execute 'doxoade gui build' primeiro.")
        
    return ctypes.CDLL(str(lib_path))

# Carregamento Dinâmico
_dxlib = _load_native_lib()

# Assinaturas C-Types
_dxlib.dxgui_create_window.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
_dxlib.dxgui_create_window.restype = ctypes.c_void_p

_dxlib.dxgui_run_loop.argtypes = []
_dxlib.dxgui_run_loop.restype = None

_dxlib.dxgui_set_click_callback.argtypes = [CALLBACK]
_dxlib.dxgui_set_click_callback.restype = None

class BenzaitenWindow:
    def __init__(self, title="Benzaiten GUI", width=800, height=600, mode="native"):
        """
        mode: "native" (GDI/X11 puros) ou "web" (HTML/CSS via WebView - Futuro)
        """
        self.mode = mode
        self._hwnd = _dxlib.dxgui_create_window(title.encode("utf-8"), width, height)
        
        if not self._hwnd:
            raise RuntimeError("Falha ao criar janela Benzaiten.")

        self._click_cb_ref = None

    def on_click(self, func):
        if self.mode == "web":
            print("[BENZAITEN] Aviso: Evento de clique nativo ignorado no modo 'web'.")
            return
            
        cb = CALLBACK(func)
        self._click_cb_ref = cb # Protege contra o Garbage Collector do Python
        _dxlib.dxgui_set_click_callback(cb)

    def run(self):
        _dxlib.dxgui_run_loop()