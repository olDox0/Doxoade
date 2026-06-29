# doxoade/doxoade/tools/benzaiten_gui/core.py
"""
BENZAITEN CORE — Camada Python sobre a DLL nativa (webview edition).

Modos:
    "native" — GDI puro (Win32)
    "web"    — webview/webview (Chromium/WebView2), HTML5 completo

Uso correto (modo web):
    win = BenzaitenWindow("App", mode="web")

    @win.on_ready
    def _ready():
        win.load_html("<h1>Olá!</h1>")

    win.run()

REGRA: load_html() e navigate() DEVEM ser chamados dentro do on_ready.
"""

import ctypes
import sys
import os
from pathlib import Path
from doxoade.tools.filesystem import _find_project_root

# ─── Tipos de callback ────────────────────────────────────────────────────────
CLICK_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
READY_CALLBACK = ctypes.CFUNCTYPE(None)
MSG_CALLBACK   = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

# ─── Carregamento da DLL ──────────────────────────────────────────────────────
def _load_native_lib() -> ctypes.CDLL:
    root     = Path(_find_project_root(os.getcwd()))
    bin_dir  = root / ".doxoade" / "benzaiten"
    lib_path = bin_dir / ("dxgui.dll" if sys.platform == "win32" else "libdxgui.so")

    if not lib_path.exists():
        raise FileNotFoundError(
            "Motor Benzaiten não compilado. Execute 'doxoade gui build' primeiro."
        )

    # Adiciona o diretório da DLL ao search path para WebView2Loader.dll
    if sys.platform == "win32":
        os.add_dll_directory(str(bin_dir))

    return ctypes.CDLL(str(lib_path))

_dxlib = _load_native_lib()

# ─── Resolução lazy de símbolos ───────────────────────────────────────────────
# Usamos getattr lazy em vez de atribuir .argtypes no import — assim uma DLL
# antiga (sem dxgui_set_msg_callback) não quebra o import inteiro.
# Os tipos são configurados uma única vez na primeira chamada.

def _bind(name, argtypes, restype):
    """Resolve e configura um símbolo da DLL. Retorna None se não existir."""
    try:
        fn = getattr(_dxlib, name)
        fn.argtypes = argtypes
        fn.restype  = restype
        return fn
    except AttributeError:
        return None

# Símbolos obrigatórios — presentes em todas as versões da DLL
_fn_create  = _bind("dxgui_create_window",
                     [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int],
                     ctypes.c_void_p)
_fn_run     = _bind("dxgui_run_loop",   [], None)
_fn_is_rdy  = _bind("dxgui_is_ready",  [], ctypes.c_int)

# Símbolos de modo native
_fn_click   = _bind("dxgui_set_click_callback", [CLICK_CALLBACK], None)

# Símbolos de modo web (webview edition — podem estar ausentes na DLL antiga)
_fn_nav     = _bind("dxgui_navigate",            [ctypes.c_void_p, ctypes.c_char_p], None)
_fn_html    = _bind("dxgui_load_html",           [ctypes.c_void_p, ctypes.c_char_p], None)
_fn_eval    = _bind("dxgui_eval_js",             [ctypes.c_void_p, ctypes.c_char_p], None)
_fn_ready   = _bind("dxgui_set_ready_callback",  [READY_CALLBACK], None)
_fn_msg     = _bind("dxgui_set_msg_callback",    [MSG_CALLBACK],   None)

# Aviso de DLL desatualizada — não aborta, apenas informa
_WEB_SYMBOLS = {"dxgui_navigate": _fn_nav, "dxgui_load_html": _fn_html,
                "dxgui_eval_js": _fn_eval, "dxgui_set_ready_callback": _fn_ready,
                "dxgui_set_msg_callback": _fn_msg}
_missing = [k for k, v in _WEB_SYMBOLS.items() if v is None]
if _missing:
    import warnings
    warnings.warn(
        f"[BENZAITEN] DLL antiga detectada — símbolos ausentes: {_missing}\n"
        f"  Modo 'web' indisponível. Execute: doxoade gui build",
        stacklevel=1
    )


# ─── Helpers internos ────────────────────────────────────────────────────────
def _require_web(fn_ref, fname: str):
    """Levanta erro claro se um símbolo web não está na DLL atual."""
    if fn_ref is None:
        raise RuntimeError(
            f"[BENZAITEN] '{fname}' não disponível — DLL antiga em disco.\n"
            f"Execute 'doxoade gui build' para compilar a versão webview."
        )


# ─── Classe principal ─────────────────────────────────────────────────────────
class BenzaitenWindow:
    """
    Janela Benzaiten.

    Parâmetros
    ----------
    title  : título da janela
    width  : largura inicial
    height : altura inicial
    mode   : "native" (GDI) | "web" (WebView2/Chromium)
    """

    def __init__(self, title: str = "Benzaiten GUI",
                 width: int = 800, height: int = 600,
                 mode: str = "native"):
        self.mode  = mode
        self._hwnd = None

        # Referências mantidas vivas contra o GC
        self._ready_cb_ref = None
        self._click_cb_ref = None
        self._msg_cb_ref   = None

        self._on_ready_fn   = None
        self._on_message_fn = None

        if mode == "web":
            _require_web(_fn_create, "dxgui_create_window")

        c_web = 1 if mode == "web" else 0
        hwnd  = _fn_create(title.encode("utf-8"), width, height, c_web)
        if not hwnd:
            raise RuntimeError("Falha ao criar janela Benzaiten.")
        self._hwnd = hwnd

    # ─── Decoradores de callback ──────────────────────────────────────────────

    def on_ready(self, fn):
        """
        Decorador: fn() chamado uma vez, antes do message loop iniciar.
        É o único momento seguro para chamar load_html() ou navigate().
        """
        self._on_ready_fn = fn
        return fn

    def on_message(self, fn):
        """Decorador: fn(msg: str) chamado quando JS executa window.__dx_send__("msg")."""
        self._on_message_fn = fn
        return fn

    def on_click(self, fn):
        """Decorador: clique no botão nativo (mode='native' apenas)."""
        if self.mode == "web":
            print("[BENZAITEN] on_click ignorado no modo 'web'. Use JS.")
            return fn
        cb = CLICK_CALLBACK(fn)
        self._click_cb_ref = cb
        if _fn_click:
            _fn_click(cb)
        return fn

    # ─── Navegação (modo web) ─────────────────────────────────────────────────

    def navigate(self, url: str):
        """Navega para uma URL. Chamar dentro do on_ready."""
        _require_web(_fn_nav, "dxgui_navigate")
        _fn_nav(self._hwnd, url.encode("utf-8"))

    def load_html(self, html: str):
        """
        Carrega HTML diretamente via webview_set_html.
        HTML5 completo — sem arquivo temporário, sem meta tags legadas.
        Chamar dentro do on_ready.
        """
        _require_web(_fn_html, "dxgui_load_html")
        _fn_html(self._hwnd, html.encode("utf-8"))

    def eval_js(self, js: str):
        """Executa JavaScript na página atual. Chamar dentro do on_ready."""
        _require_web(_fn_eval, "dxgui_eval_js")
        _fn_eval(self._hwnd, js.encode("utf-8"))

    # ─── Loop principal ───────────────────────────────────────────────────────

    def run(self):
        """
        Inicia o message loop. Bloqueia até a janela ser fechada.
        O on_ready dispara dentro do dxgui_run_loop, antes do loop iniciar.
        """
        if self.mode == "web":
            # Registra ready callback
            if self._on_ready_fn and _fn_ready:
                cb = READY_CALLBACK(self._on_ready_fn)
                self._ready_cb_ref = cb
                _fn_ready(cb)

            # Registra message callback
            if self._on_message_fn and _fn_msg:
                fn = self._on_message_fn
                def _msg_wrapper(raw: bytes):
                    try:
                        fn(raw.decode("utf-8") if raw else "")
                    except Exception:
                        pass
                cb2 = MSG_CALLBACK(_msg_wrapper)
                self._msg_cb_ref = cb2
                _fn_msg(cb2)

        _fn_run()

    # ─── Status ───────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return bool(_fn_is_rdy()) if _fn_is_rdy else False