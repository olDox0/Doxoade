# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/renderer.py
"""FASE 1 — ponte ctypes do modo Soft (buffer BGRA + teclado)."""
import ctypes, sys, os
from pathlib import Path
from doxoade.tools.filesystem import _find_project_root

KEY_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)
RESIZE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
CLICK_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
MOUSE_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_int)
_WM_APP_REPAINT = 0x0400 + 92

def _load_lib():
    root = Path(_find_project_root(os.getcwd()))
    bin_dir = root / '.doxoade' / 'benzaiten'
    lib_path = bin_dir / ('dxgui.dll' if sys.platform == 'win32' else 'libdxgui.so')
    if not lib_path.exists():
        raise FileNotFoundError('Motor Benzaiten não compilado. Rode: doxoade gui build')
    if sys.platform == 'win32':
        os.add_dll_directory(str(bin_dir))
    return ctypes.CDLL(str(lib_path))

class SoftRenderer:
    def __init__(self, title='SoftClub', width=800, height=600):
        self.lib = _load_lib()
        self.w, self.h = width, height
        L = self.lib
        L.dxgui_create_window.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        L.dxgui_create_window.restype  = ctypes.c_void_p
        L.dxgui_run_loop.argtypes = [];            L.dxgui_run_loop.restype = None
#        L.dxgui_present.argtypes  = [ctypes.c_void_p, ctypes.c_int]; L.dxgui_present.restype = ctypes.c_int
        L.dxgui_present.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        L.dxgui_present.restype  = ctypes.c_int
        L.dxgui_set_resize_callback.argtypes = [RESIZE_CALLBACK]
        L.dxgui_get_client_size.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        L.dxgui_set_key_callback.argtypes = [KEY_CB]; L.dxgui_set_key_callback.restype = None
        L.dxgui_quit.argtypes = [];                L.dxgui_quit.restype = None
        self._hwnd = L.dxgui_create_window(title.encode('utf-8'), width, height, 2)
        if not self._hwnd:
            raise RuntimeError('Falha ao criar janela SoftClub (modo soft). DLL antiga? Rode: doxoade gui build')
        self._cb_ref = None
        self._buf = None
        self._repaint_py = None
        self._repaint_pending = False
        if hasattr(self, '_install_subclass'):
            self._install_subclass()

    def client_size(self):
        w, h = ctypes.c_int(0), ctypes.c_int(0)
        self.lib.dxgui_get_client_size(ctypes.byref(w), ctypes.byref(h))
        return (w.value or self.w, h.value or self.h)

    def on_resize(self, fn):
        def _wrap(w, h): fn(w, h)
        self._resize_cb_ref = RESIZE_CALLBACK(_wrap)   # protege do GC
        self.lib.dxgui_set_resize_callback(self._resize_cb_ref)

    def present(self, bgra, w, h):
        self._buf = (ctypes.c_ubyte * len(bgra)).from_buffer_copy(bgra)
        return bool(self.lib.dxgui_present(self._buf, w, h))

    def on_key(self, fn):
        def _wrap(vk, text):
            fn(vk, text.decode('utf-8', 'ignore') if text else '')
        self._cb_ref = KEY_CB(_wrap)               # protege do GC
        self.lib.dxgui_set_key_callback(self._cb_ref)

    def on_drop(self, fn):
        drop_t = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        def _wrap(path):
            if os.environ.get('SOFTCLUB_DEBUG') == '1':
                sys.stderr.write(f"[SOFTCLUB-DEBUG] drop cb recebeu: {path!r}\n"); sys.stderr.flush()
            fn(path.decode('utf-8', 'ignore') if path else '')
        self._drop_cb_ref = drop_t(_wrap)
        try:
            L = self.lib
            L.dxgui_set_drop_callback.argtypes = [drop_t]
            L.dxgui_set_drop_callback.restype = None
            L.dxgui_set_drop_callback(self._drop_cb_ref)
        except AttributeError:
            self._drop_cb_ref = None   # DLL antiga: drop inativo, resto funciona

    def on_click(self, fn):
        def _wrap(x, y): fn(x, y)
        self._click_cb_ref = CLICK_CB(_wrap)
        try:
            L = self.lib
            L.dxgui_set_click_callback.argtypes = [CLICK_CB]
            L.dxgui_set_click_callback.restype = None
            L.dxgui_set_click_callback(self._click_cb_ref)
        except AttributeError:
            self._click_cb_ref = None

    def on_mouse(self, fn):
        def _wrap(x, y, buttons): fn(x, y, buttons)
        self._mouse_cb_ref = MOUSE_CB(_wrap)
        try:
            L = self.lib
            L.dxgui_set_mouse_callback.argtypes = [MOUSE_CB]
            L.dxgui_set_mouse_callback.restype = None
            L.dxgui_set_mouse_callback(self._mouse_cb_ref)
        except AttributeError:
            self._mouse_cb_ref = None

    def style_titlebar(self, dark, border_rgb, caption_rgb):
        try:
            fn = self.lib.dxgui_set_titlebar_style
            fn.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
            fn.restype = None
            cref = lambda c: (c[2] << 16) | (c[1] << 8) | c[0]
            fn(1 if dark else 0, cref(border_rgb), cref(caption_rgb))
        except AttributeError:
            pass

    def set_frameless(self, on):
        try:
            fn = self.lib.dxgui_set_frameless
            fn.argtypes = [ctypes.c_int]; fn.restype = None
            fn(1 if on else 0)
        except AttributeError:
            pass
    def win_minimize(self):
        try: self.lib.dxgui_win_minimize()
        except AttributeError: pass
    def win_maximize(self):
        try: self.lib.dxgui_win_maximize()
        except AttributeError: pass
    def win_close(self):
        try: self.lib.dxgui_win_close()
        except AttributeError: pass
    def start_drag(self):
        try: self.lib.dxgui_start_drag()
        except AttributeError: pass

    def set_title(self, text):
        try:
            fn = self.lib.dxgui_set_title
            fn.argtypes = [ctypes.c_char_p]
            fn.restype = None
            fn(text.encode('utf-8'))
        except AttributeError:
            pass   # DLL antiga: título fica o de criação

    def request_repaint(self):
        # v22: SEMPRE via PostMessage (thread-safe). Worker/animator
        # nunca chamam a DLL => sem race, sem no-op de thread estranha.
        self.request_repaint_safe()

    def request_repaint_safe(self):
        """Thread-safe: PostMessage → WndProc subclassado → paint Python
        no loop principal. Zero GDI de thread estranha, zero race."""
        try:
            u = ctypes.windll.user32
            if not getattr(self, '_pm_bound', False):
                u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.c_uint64, ctypes.c_int64]
                u.PostMessageW.restype = ctypes.c_int
                self._pm_bound = True
            if getattr(self, '_repaint_pending', False):
                return
            self._repaint_pending = True
            u.PostMessageW(self._hwnd, _WM_APP_REPAINT, 0, 0)
        except Exception:
            pass

    def on_repaint(self, fn):
        """Registra o pump Python e subclassa a janela (1x)."""
        self._repaint_py = fn
        self._install_subclass()

    def _install_subclass(self):
        if getattr(self, '_subclassed', False):
            return
        try:
            u = ctypes.windll.user32
            GWLP_WNDPROC = -4
            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_void_p,
                                         ctypes.c_uint, ctypes.c_uint64, ctypes.c_int64)
            u.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_uint, ctypes.c_uint64, ctypes.c_int64]
            u.CallWindowProcW.restype = ctypes.c_int64
            u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            u.SetWindowLongPtrW.restype = ctypes.c_void_p

            def _proc(hwnd, msg, wp, lp):
                if msg == _WM_APP_REPAINT:
                    self._repaint_pending = False
                    fn = getattr(self, '_repaint_py', None)
                    if fn:
                        try:
                            fn()
                        except Exception:
                            pass
                    return 0
                return u.CallWindowProcW(self._old_proc, hwnd, msg, wp, lp)

            self._wndproc_ref = WNDPROC(_proc)
            self._old_proc = u.SetWindowLongPtrW(self._hwnd, GWLP_WNDPROC,
                                                 self._wndproc_ref)
            self._subclassed = True
            import sys
            sys.stderr.write('[SOFTCLUB-DEBUG] repaint hook instalado (WndProc subclass)\n')
            sys.stderr.flush()
        except Exception as e:
            import sys
            sys.stderr.write(f'[SOFTCLUB-DEBUG] ⚠ subclass falhou: {e}\n')
            sys.stderr.flush()

    def run(self):
        _dbg_run = os.environ.get('SOFTCLUB_DEBUG') == '1'
        if _dbg_run:
            sys.stderr.write("[SOFTCLUB-DEBUG] entering dxgui_run_loop\n"); sys.stderr.flush()
        self.lib.dxgui_run_loop()
        if _dbg_run:
            sys.stderr.write("[SOFTCLUB-DEBUG] left dxgui_run_loop\n"); sys.stderr.flush()
    def quit(self): self.lib.dxgui_quit()