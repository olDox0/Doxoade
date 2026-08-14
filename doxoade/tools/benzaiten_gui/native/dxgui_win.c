// doxoade/tools/benzaiten_gui/native/dxgui_win.c
// BENZAITEN ENGINE — Windows Backend (webview + soft) COM SOTERIA
//
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#define WEBVIEW_API __declspec(dllexport)

#ifndef WM_COPYGLOBALDATA
#define WM_COPYGLOBALDATA 0x0049
#endif
#ifndef MSGFLT_ALLOW
#define MSGFLT_ALLOW 1
#endif

#include "include/webview.h"
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <functional>
#include <stdio.h>
#include <stdlib.h>

// SOTERIA TAGS para diagnóstico
#define SOTERIA_BEGIN "@SOTERIA_BEGIN@\n"
#define SOTERIA_END   "@SOTERIA_END@\n"
#define TAG_LEVEL  "TAG_LEVEL: "
#define TAG_MOTIVO "TAG_MOTIVO: "
#define TAG_DETAIL "TAG_DETAIL: "
#define TAG_RASTRO "TAG_RASTRO_LOC: "
#define TAG_FRAME  "TAG_FRAME: "

#define DX_EXPORT extern "C" __declspec(dllexport)

typedef void (*dxgui_ready_cb)(void);
typedef void (*dxgui_click_cb)(int x, int y);
typedef void (*dxgui_msg_cb)(const char* msg);

static webview_t   g_wv        = nullptr;
static int         g_web_mode  = 0;
static dxgui_ready_cb g_ready_cb = nullptr;
static dxgui_msg_cb   g_msg_cb   = nullptr;
static dxgui_click_cb g_click_cb = nullptr;
static std::string g_pending_html;
static std::string g_pending_url;

// SOTERIA: Macro para capturar exceções
#define SOTERIA_CATCH(tag, detail) \
    catch (const std::exception& e) { \
        fprintf(stderr, SOTERIA_BEGIN); \
        fprintf(stderr, TAG_LEVEL "FATAL\n"); \
        fprintf(stderr, TAG_MOTIVO "%s\n", tag); \
        fprintf(stderr, TAG_DETAIL "%s: %s\n", detail, e.what()); \
        fprintf(stderr, TAG_RASTRO "%s:%d\n", __FILE__, __LINE__); \
        fprintf(stderr, SOTERIA_END); \
        fflush(stderr); \
    } \
    catch (...) { \
        fprintf(stderr, SOTERIA_BEGIN); \
        fprintf(stderr, TAG_LEVEL "FATAL\n"); \
        fprintf(stderr, TAG_MOTIVO "%s\n", tag); \
        fprintf(stderr, TAG_DETAIL "Unknown exception in %s\n", detail); \
        fprintf(stderr, TAG_RASTRO "%s:%d\n", __FILE__, __LINE__); \
        fprintf(stderr, SOTERIA_END); \
        fflush(stderr); \
    }

// ─── SOFT MODE (mode 2): BGRA + teclado + resize ────────────────────────────
// ORDEM CANÔNICA: typedefs → globals → WndProc → exports (C exige declaração antes do uso)
typedef void (*dxgui_key_cb)(int vk, const char* utf8_text);
typedef void (*dxgui_resize_cb)(int w, int h);
typedef void (*dxgui_drop_cb)(const char* utf8_path);

static HWND  g_soft_hwnd  = nullptr;
static void* g_src_copy   = nullptr;   // último buffer apresentado (cópia C)
static void*      g_dib_bits = nullptr;
static HBITMAP    g_dib_bmp  = nullptr;
static int        g_dib_w    = 0;
static int        g_dib_h    = 0;
static int   g_src_w = 0, g_src_h = 0;
static int   g_client_w = 0, g_client_h = 0;
static dxgui_key_cb    g_key_cb    = nullptr;
static dxgui_resize_cb g_resize_cb = nullptr;
static dxgui_drop_cb g_drop_cb = nullptr;

typedef void (*dxgui_mouse_cb)(int x, int y, int buttons);
static dxgui_mouse_cb g_mouse_cb = nullptr;
static int g_tracking = 0;

DX_EXPORT void dxgui_set_mouse_callback(dxgui_mouse_cb cb) {
    g_mouse_cb = cb; 
}

#define SOFT_RENDER_TIMER 999

// ─── HORUS-NATIVE TRACER v1 (DXGUI_TRACE=1) ──────────────────────
#include <stdarg.h>
static FILE* g_trace_fp = NULL;
static int   g_trace_on = -1;
static DWORD g_t0 = 0;

static void dxtrace(const char* fmt, ...) {
    if (g_trace_on < 0) {
        g_trace_on = (getenv("DXGUI_TRACE") != NULL) ? 1 : 0;
        g_t0 = GetTickCount();
        if (g_trace_on) g_trace_fp = fopen("dxgui_trace.log", "w");
    }
    if (!g_trace_on || !g_trace_fp) return;
    fprintf(g_trace_fp, "[%6lu] ", (unsigned long)(GetTickCount() - g_t0));
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_trace_fp, fmt, ap);
    va_end(ap);
    fputc('\n', g_trace_fp);
    fflush(g_trace_fp);
}

static bool soft_ensure_dib(int w, int h);
static void soft_restretch(void);

static LRESULT CALLBACK SoftWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_LBUTTONDOWN:
        if (g_click_cb || g_mouse_cb) {
            int mx = LOWORD(lp), my = HIWORD(lp);
            SetCapture(hwnd);
            if (g_click_cb) g_click_cb(mx, my);
            if (g_mouse_cb) g_mouse_cb(mx, my, 1);
        }
        return 0;
    case WM_MOUSEMOVE:
        if (g_mouse_cb) {
            g_mouse_cb(LOWORD(lp), HIWORD(lp), (wp & MK_LBUTTON) ? 1 : 0);
        }
        if (!g_tracking) {
            TRACKMOUSEEVENT tme;
            tme.cbSize    = sizeof(tme);
            tme.dwFlags   = TME_LEAVE;
            tme.hwndTrack = hwnd;
            tme.dwHoverTime = 0;
            g_tracking = TrackMouseEvent(&tme) ? 1 : 0;
        }
        return 0;
    case WM_MOUSELEAVE:
        g_tracking = 0;
        if (g_mouse_cb) g_mouse_cb(-1, -1, 0);   // limpa hover fora da janela
        return 0;
    case WM_LBUTTONUP:
        if (g_mouse_cb) {
            if (GetCapture() == hwnd) ReleaseCapture();
            g_mouse_cb(LOWORD(lp), HIWORD(lp), 0);
        }
        return 0;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        if (g_dib_bmp) {
            HDC mem = CreateCompatibleDC(dc);
            HBITMAP old = (HBITMAP)SelectObject(mem, g_dib_bmp);
            BitBlt(dc, 0, 0, g_dib_w, g_dib_h, mem, 0, 0, SRCCOPY);
            SelectObject(mem, old);
            DeleteDC(mem);
        } else {
            RECT rc; GetClientRect(hwnd, &rc);
            FillRect(dc, &rc, (HBRUSH)GetStockObject(BLACK_BRUSH));
        }
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_SIZE:
        g_client_w = LOWORD(lp); g_client_h = HIWORD(lp);
        dxtrace("WM_SIZE %d x %d", g_client_w, g_client_h);
        soft_restretch();
        InvalidateRect(hwnd, nullptr, FALSE);
        SetTimer(hwnd, SOFT_RENDER_TIMER, 120, nullptr);
        return 0;
    case WM_TIMER:
        if (wp == SOFT_RENDER_TIMER) {
            KillTimer(hwnd, SOFT_RENDER_TIMER);
            dxtrace("WM_TIMER fire -> resize_cb=%p", (void*)g_resize_cb);
            if (g_resize_cb) g_resize_cb(g_client_w, g_client_h);
        }
        return 0;
    case WM_CHAR: {
        if (g_key_cb) {
            wchar_t wc = (wchar_t)wp;
            char utf8[8] = {0};
            WideCharToMultiByte(CP_UTF8, 0, &wc, 1, utf8, 7, nullptr, nullptr);
            g_key_cb(0, utf8);
        }
        return 0;
    }
    case WM_KEYDOWN: {
        switch (wp) {
        case VK_BACK: case VK_RETURN: case VK_TAB: case VK_ESCAPE:
        case VK_UP: case VK_DOWN: case VK_LEFT: case VK_RIGHT:
        case VK_HOME: case VK_END: case VK_DELETE:
        case VK_F1: case VK_F4: case VK_F5:
            if (g_key_cb) g_key_cb((int)wp, "");
            return 0;
        }
        return 0;
    }
    case WM_DROPFILES: {
        HDROP hdrop = (HDROP)wp;
        dxtrace("WM_DROPFILES hdrop=%p cb=%p", (void*)wp, (void*)g_drop_cb);
        unsigned char* p = (unsigned char*)GlobalLock(hdrop);
        if (p && g_drop_cb) {
            DWORD off = *(DWORD*)p;
            BOOL wide = *(BOOL*)(p + 16);
            unsigned char* list = p + off;
            if (wide) {
                char utf8[1024] = {0};
                WideCharToMultiByte(CP_UTF8, 0, (wchar_t*)list, -1, utf8, 1023, nullptr, nullptr);
                dxtrace("drop path: %s", utf8);
                g_drop_cb(utf8);
            } else {
                dxtrace("drop path(ansi): %s", list);
                g_drop_cb((const char*)list);
            }
        }
        if (p) GlobalUnlock(hdrop);
        return 0;
    }
    case WM_APP + 1:   // repaint pedido de outra thread (thread-safe)
        if (g_resize_cb) g_resize_cb(g_client_w, g_client_h);
        return 0;
    case WM_CLOSE:  dxtrace("WM_CLOSE"); DestroyWindow(hwnd); return 0;
    case WM_DESTROY: dxtrace("WM_DESTROY"); PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

DX_EXPORT void* dxgui_create_window(const char* title, int width, int height, int web_mode) {
    g_web_mode = web_mode;
    if (web_mode == 1) {
        try {
            g_wv = webview_create(0, nullptr);
            if (!g_wv) {
                fprintf(stderr, SOTERIA_BEGIN);
                fprintf(stderr, TAG_LEVEL "FATAL\n");
                fprintf(stderr, TAG_MOTIVO "WEBVIEW_CREATE_FAILED\n");
                fprintf(stderr, TAG_DETAIL "webview_create returned null\n");
                fprintf(stderr, SOTERIA_END);
                return nullptr;
            }
            webview_set_title(g_wv, title);
            webview_set_size(g_wv, width, height, WEBVIEW_HINT_NONE);
            webview_bind(g_wv, "__dx_send__", [](const char* seq, const char* req, void* arg) {
                try {
                    dxgui_msg_cb cb = (dxgui_msg_cb)arg;
                    if (cb) cb(req);
                } SOTERIA_CATCH("JS_CALLBACK_CRASH", "__dx_send__ callback")
            }, (void*)g_msg_cb);
            webview_navigate(g_wv, "about:blank");
            return (void*)g_wv;
        } SOTERIA_CATCH("WINDOW_CREATE_CRASH", "dxgui_create_window")
    } else if (web_mode == 2) {
        // ── SOFT: GDI + StretchDIBits + teclado + resize ──
        HINSTANCE hInst = GetModuleHandle(nullptr);
        WNDCLASSW wc = {};
        wc.lpfnWndProc   = SoftWndProc;
        wc.hInstance     = hInst;
        wc.hCursor       = LoadCursor(nullptr, IDC_ARROW);
        wc.lpszClassName = L"DXGUI_Soft";
        RegisterClassW(&wc);
        wchar_t wtitle[256] = {};
        MultiByteToWideChar(CP_UTF8, 0, title, -1, wtitle, 256);
        RECT rc = { 0, 0, width, height };
        AdjustWindowRect(&rc, WS_OVERLAPPEDWINDOW, FALSE);   // cliente = WxH exatos
//        HWND hwnd = CreateWindowExW(0, L"DXGUI_Soft", wtitle, WS_OVERLAPPEDWINDOW,
        HWND hwnd = CreateWindowExW(WS_EX_ACCEPTFILES, L"DXGUI_Soft", wtitle, WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT, CW_USEDEFAULT, rc.right - rc.left, rc.bottom - rc.top,
            nullptr, nullptr, hInst, nullptr);
        if (!hwnd) return nullptr;
        RECT cr; GetClientRect(hwnd, &cr);
        g_client_w = cr.right - cr.left; g_client_h = cr.bottom - cr.top;
        g_soft_hwnd = hwnd;
        dxtrace("create soft hwnd=%p client=%dx%d", (void*)hwnd, g_client_w, g_client_h);
        SetWindowLongPtrW(g_soft_hwnd, GWL_EXSTYLE,
                          GetWindowLongPtrW(g_soft_hwnd, GWL_EXSTYLE) | WS_EX_ACCEPTFILES);
        ChangeWindowMessageFilterEx(g_soft_hwnd, WM_DROPFILES, MSGFLT_ALLOW, NULL);
        ChangeWindowMessageFilterEx(g_soft_hwnd, WM_COPYGLOBALDATA, MSGFLT_ALLOW, NULL);
        ShowWindow(hwnd, SW_SHOW);
        UpdateWindow(hwnd);
        return (void*)hwnd;
    } else {
        // Modo native (GDI)
        HINSTANCE hInst = GetModuleHandle(nullptr);
        WNDCLASSW wc = {};
        wc.lpfnWndProc = DefWindowProcW;
        wc.hInstance = hInst;
        wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
        wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
        wc.lpszClassName = L"DXGUI_Native";
        RegisterClassW(&wc);
        wchar_t wtitle[256] = {};
        MultiByteToWideChar(CP_UTF8, 0, title, -1, wtitle, 256);
        HWND hwnd = CreateWindowExW(
            0, L"DXGUI_Native", wtitle,
            WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT, CW_USEDEFAULT, width, height,
            nullptr, nullptr, hInst, nullptr
        );
        if (!hwnd) return nullptr;
        ShowWindow(hwnd, SW_SHOW);
        UpdateWindow(hwnd);
        return (void*)hwnd;
    }
    return nullptr;
}

// ─── SOFT exports ────────────────────────────────────────────────────────────
DX_EXPORT void dxgui_set_key_callback(dxgui_key_cb cb) { g_key_cb = cb; }
DX_EXPORT void dxgui_set_resize_callback(dxgui_resize_cb cb) { g_resize_cb = cb; }

typedef void (*dxgui_drop_cb)(const char* utf8_path);
//static dxgui_drop_cb g_drop_cb = nullptr;

DX_EXPORT void dxgui_set_drop_callback(dxgui_drop_cb cb) { g_drop_cb = cb; }
DX_EXPORT void dxgui_request_repaint(void) {
    if (g_soft_hwnd) PostMessageW(g_soft_hwnd, WM_APP + 1, 0, 0);
}

DX_EXPORT void dxgui_set_titlebar_style(int dark, unsigned int border_bgr, unsigned int caption_bgr) {
    if (!g_soft_hwnd) return;
    HMODULE hDwm = LoadLibraryW(L"dwmapi.dll");   // runtime: sem -ldwmapi no build
    if (!hDwm) return;
    typedef HRESULT (WINAPI *PFN_DwmSetAttr)(HWND, DWORD, LPCVOID, DWORD);
    PFN_DwmSetAttr pSet = (PFN_DwmSetAttr)GetProcAddress(hDwm, "DwmSetWindowAttribute");
    if (pSet) {
        BOOL dv = dark ? 1 : 0;
        pSet(g_soft_hwnd, 20, &dv, sizeof(dv));     // IMMERSIVE_DARK_MODE (Win10 1809+)
        COLORREF bc = (COLORREF)border_bgr;          // Win11: borda da janela
        COLORREF cc = (COLORREF)caption_bgr;         // Win11: caption
        pSet(g_soft_hwnd, 34, &bc, sizeof(bc));
        pSet(g_soft_hwnd, 36, &cc, sizeof(cc));
    }
    FreeLibrary(hDwm);
}

// ─── SOFT: titlebar custom (frameless) ─────────────────────────────
DX_EXPORT void dxgui_set_frameless(int on) {
    if (!g_soft_hwnd) return;
    LONG_PTR st = GetWindowLongPtrW(g_soft_hwnd, GWL_STYLE);
    if (on) st &= ~(WS_CAPTION | WS_SYSMENU);   // mata barra/botões nativos
    else    st |=  (WS_CAPTION | WS_SYSMENU);
    SetWindowLongPtrW(g_soft_hwnd, GWL_STYLE, st);
    SetWindowPos(g_soft_hwnd, nullptr, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
    RECT rc; GetClientRect(g_soft_hwnd, &rc);
    g_client_w = rc.right - rc.left; g_client_h = rc.bottom - rc.top;
    soft_restretch();
    InvalidateRect(g_soft_hwnd, nullptr, FALSE);
}
DX_EXPORT void dxgui_win_minimize(void) {
    if (g_soft_hwnd) ShowWindow(g_soft_hwnd, SW_MINIMIZE);
}
DX_EXPORT void dxgui_win_maximize(void) {
    if (!g_soft_hwnd) return;
    if (IsZoomed(g_soft_hwnd)) ShowWindow(g_soft_hwnd, SW_RESTORE);
    else ShowWindow(g_soft_hwnd, SW_MAXIMIZE);
}
DX_EXPORT void dxgui_win_close(void) {
    if (g_soft_hwnd) PostMessageW(g_soft_hwnd, WM_CLOSE, 0, 0);
}
DX_EXPORT void dxgui_start_drag(void) {
    if (!g_soft_hwnd) return;
    ReleaseCapture();
    SendMessageW(g_soft_hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0);
}

DX_EXPORT void dxgui_set_title(const char* utf8) {
    if (!g_soft_hwnd) return;
    wchar_t wtitle[512] = {};
    MultiByteToWideChar(CP_UTF8, 0, utf8, -1, wtitle, 511);
    SetWindowTextW(g_soft_hwnd, wtitle);
}

static bool soft_ensure_dib(int w, int h) {
    if (g_dib_bmp && g_dib_w == w && g_dib_h == h) return true;
    if (g_dib_bmp) { DeleteObject(g_dib_bmp); g_dib_bmp = nullptr; g_dib_bits = nullptr; }
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w; bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    g_dib_bmp = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &g_dib_bits, nullptr, 0);
    g_dib_w = w; g_dib_h = h;
    return g_dib_bmp != nullptr;
}

static void soft_restretch(void) {
    if (!g_src_copy || g_src_w <= 0 || g_src_h <= 0) return;
    int cw = g_client_w > 0 ? g_client_w : g_src_w;
    int ch = g_client_h > 0 ? g_client_h : g_src_h;
    if (!soft_ensure_dib(cw, ch)) return;
    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = g_src_w; bmi.bmiHeader.biHeight = -g_src_h;
    bmi.bmiHeader.biPlanes = 1; bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;
    HDC mem = CreateCompatibleDC(NULL);
    HBITMAP old = (HBITMAP)SelectObject(mem, g_dib_bmp);
    SetStretchBltMode(mem, HALFTONE);
    SetBrushOrgEx(mem, 0, 0, nullptr);
    StretchDIBits(mem, 0, 0, cw, ch, 0, 0, g_src_w, g_src_h,
                  g_src_copy, &bmi, DIB_RGB_COLORS, SRCCOPY);
    SelectObject(mem, old);
    DeleteDC(mem);
}

static HDC soft_draw_begin(HBITMAP* old_bmp) {
    HDC mem = CreateCompatibleDC(NULL);
    *old_bmp = (HBITMAP)SelectObject(mem, g_dib_bmp);
    return mem;
}

static void soft_draw_end(HDC mem, HBITMAP old_bmp) {
    SelectObject(mem, old_bmp);
    DeleteDC(mem);
    if (g_soft_hwnd) InvalidateRect(g_soft_hwnd, nullptr, FALSE);
}

DX_EXPORT int dxgui_present(const void* bgra, int w, int h) {
    if (!bgra || w <= 0 || h <= 0) return 0;
    size_t need = (size_t)w * h * 4;
    free(g_src_copy);
    g_src_copy = malloc(need);
    if (!g_src_copy) { g_src_w = g_src_h = 0; return 0; }
    memcpy(g_src_copy, bgra, need);
    dxtrace("present %dx%d", w, h);
    g_src_w = w; g_src_h = h;
    soft_restretch();
    if (g_soft_hwnd) InvalidateRect(g_soft_hwnd, nullptr, FALSE);
    return 1;
}

DX_EXPORT void dxgui_invalidate(void) {
    if (g_soft_hwnd) InvalidateRect(g_soft_hwnd, nullptr, FALSE);
}

DX_EXPORT void dxgui_get_client_size(int* w, int* h) {
    if (w) *w = g_client_w;
    if (h) *h = g_client_h;
}

DX_EXPORT void dxgui_quit(void) {
    dxtrace("dxgui_quit chamado");
    if (g_soft_hwnd) DestroyWindow(g_soft_hwnd);
    PostQuitMessage(0);
}

// ─── Webview exports ─────────────────────────────────────────────────────────
DX_EXPORT void dxgui_set_ready_callback(dxgui_ready_cb cb) { g_ready_cb = cb; }
DX_EXPORT void dxgui_set_click_callback(dxgui_click_cb cb) { g_click_cb = cb; }

DX_EXPORT void dxgui_set_msg_callback(dxgui_msg_cb cb) {
    g_msg_cb = cb;
    if (g_web_mode && g_wv && cb) {
        try {
            webview_unbind(g_wv, "__dx_send__");
            webview_bind(g_wv, "__dx_send__", [](const char* seq, const char* req, void* arg) {
                try {
                    dxgui_msg_cb callback = (dxgui_msg_cb)arg;
                    if (callback) callback(req);
                } SOTERIA_CATCH("MSG_CALLBACK_REBIND_CRASH", "dxgui_set_msg_callback")
            }, (void*)g_msg_cb);
        } SOTERIA_CATCH("MSG_BIND_CRASH", "dxgui_set_msg_callback")
    }
}

DX_EXPORT void dxgui_navigate(void* handle, const char* url) {
    if (!g_wv || !url) return;
    try {
        std::string url_copy(url);
        webview_dispatch(g_wv, [](webview_t wv, void* arg) {
            try {
                std::string* s = (std::string*)arg;
                webview_navigate(wv, s->c_str());
                delete s;
            } SOTERIA_CATCH("NAVIGATE_DISPATCH_CRASH", "dxgui_navigate dispatch")
        }, new std::string(url_copy));
    } SOTERIA_CATCH("NAVIGATE_CRASH", "dxgui_navigate")
}

DX_EXPORT void dxgui_load_html(void* handle, const char* html) {
    if (!g_wv || !html) return;
    try {
        std::string html_copy(html);
        webview_dispatch(g_wv, [](webview_t wv, void* arg) {
            try {
                std::string* s = (std::string*)arg;
                webview_set_html(wv, s->c_str());
                delete s;
            } SOTERIA_CATCH("LOAD_HTML_DISPATCH_CRASH", "dxgui_load_html dispatch")
        }, new std::string(html_copy));
    } SOTERIA_CATCH("LOAD_HTML_CRASH", "dxgui_load_html")
}

DX_EXPORT void dxgui_eval_js(void* handle, const char* js) {
    if (!g_wv || !js) return;
    std::string wrapped_js =
        std::string("(function() { ") +
        "try { " +
        "if (document.readyState === 'loading') { " +
        "  document.addEventListener('DOMContentLoaded', function() { " +
        "    try { " + std::string(js) + " } catch(e) { console.error('[DXGUI Eval Error]:', e); } " +
        "  }); " +
        "} else { " +
        "  try { " + std::string(js) + " } catch(e) { console.error('[DXGUI Eval Error]:', e); } " +
        "} " +
        "} catch(e) { console.error('[DXGUI Wrapper Error]:', e); } " +
        "})();";
    std::string* js_copy = new std::string(wrapped_js);
    webview_dispatch(g_wv, [](webview_t wv, void* arg) {
        std::string* script = static_cast<std::string*>(arg);
        int result = webview_eval(wv, script->c_str());
        if (result != 0) {
            fprintf(stderr, SOTERIA_BEGIN);
            fprintf(stderr, TAG_LEVEL "ERROR\n");
            fprintf(stderr, TAG_MOTIVO "WEBVIEW_EVAL_FAILED\n");
            fprintf(stderr, TAG_DETAIL "webview_eval returned error code %d\n", result);
            fprintf(stderr, SOTERIA_END);
            fflush(stderr);
        }
        delete script;
    }, js_copy);
}

DX_EXPORT int dxgui_is_ready(void) {
    return (g_wv != nullptr) ? 1 : 0;
}

static int _dx_verbose(void) {
    static int v = -1;
    if (v < 0) v = (getenv("DXGUI_VERBOSE") != NULL) ? 1 : 0;
    return v;
}

DX_EXPORT void dxgui_run_loop(void) {
    dxtrace("run_loop start mode=%d wv=%p", g_web_mode, (void*)g_wv);
    if (g_web_mode == 1 && g_wv) {
        try {
            if (g_ready_cb) g_ready_cb();
            if (_dx_verbose()) {
                fprintf(stdout, SOTERIA_BEGIN);
                fprintf(stdout, TAG_LEVEL "INFO\n");
                fprintf(stdout, TAG_MOTIVO "RUN_LOOP_START\n");
                fprintf(stdout, TAG_DETAIL "About to call webview_run\n");
                fprintf(stdout, SOTERIA_END);
                fflush(stdout);
            }
            webview_run(g_wv);
            if (_dx_verbose()) {
                fprintf(stdout, SOTERIA_BEGIN);
                fprintf(stdout, TAG_LEVEL "INFO\n");
                fprintf(stdout, TAG_MOTIVO "RUN_LOOP_DONE\n");
                fprintf(stdout, TAG_DETAIL "webview_run finished\n");
                fprintf(stdout, SOTERIA_END);
                fflush(stdout);
            }
        } SOTERIA_CATCH("RUN_LOOP_CRASH", "dxgui_run_loop")
    } else {
        MSG msg;
        msg.message = 0;
        MSG peek;
        if (PeekMessageW(&peek, NULL, WM_QUIT, WM_QUIT, PM_REMOVE)) {
            dxtrace("STRAY WM_QUIT no boot -> drenado (wparam=%ld)", (long)peek.wParam);
        }
        dxtrace("run_loop ENTER");
        BOOL ok;
        while ((ok = GetMessage(&msg, NULL, 0, 0)) > 0) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        dxtrace("run_loop EXIT ok=%ld last_msg=0x%04X wparam=%ld gle=%lu",
                (long)ok, (unsigned)msg.message, (long)msg.wParam,
                (unsigned long)GetLastError());
    }
}

DX_EXPORT void dxgui_fill_rect(int x, int y, int w, int h, unsigned int color) {
    if (!g_dib_bmp || w <= 0 || h <= 0) return;
    HBITMAP old;
    HDC mem = soft_draw_begin(&old);
    HBRUSH br = CreateSolidBrush((COLORREF)color);
    RECT rc = { x, y, x + w, y + h };
    FillRect(mem, &rc, br);
    DeleteObject(br);
    soft_draw_end(mem, old);
}

// ─── SoftKit: desenho de texto no DIB ───────────────────────────────────────
// Assinatura esperada por kit.py:
//   draw_text(utf8, x, y, color_bgr, size, spacing) -> int (largura em px)
DX_EXPORT int dxgui_draw_text(const char* utf8, int x, int y,
                              unsigned int color, int px, int spacing) {
    if (!g_dib_bmp || !utf8 || !*utf8) return x;

    // UTF-8 → Wide
    int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, -1, nullptr, 0);
    if (wlen <= 1) return x;
    wchar_t* wbuf = (wchar_t*)malloc((size_t)wlen * sizeof(wchar_t));
    if (!wbuf) return x;
    MultiByteToWideChar(CP_UTF8, 0, utf8, -1, wbuf, wlen);
    wlen--;  // exclui null-terminator

    HBITMAP old;
    HDC mem = soft_draw_begin(&old);

    // Fonte proporcional ao tamanho pedido
    HFONT hFont = CreateFontW(
        -px, 0, 0, 0,
        FW_NORMAL,
        FALSE, FALSE, FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,  // ← Melhor qualidade
        DEFAULT_PITCH | FF_SWISS,
        L"Segoe UI"
    );

    HFONT oldFont = (HFONT)SelectObject(mem, hFont);
    SetTextColor(mem, (COLORREF)color);
    SetBkMode(mem, TRANSPARENT);
    SetTextCharacterExtra(mem, spacing);

    // ← CORREÇÃO: desenha a string INTEIRA de uma vez, não caractere por caractere
    TextOutW(mem, x, y, wbuf, wlen);

    // Mede a largura TOTAL para retorno correto
    SIZE sz = {};
    GetTextExtentPoint32W(mem, wbuf, wlen, &sz);

    SelectObject(mem, oldFont);
    DeleteObject(hFont);
    soft_draw_end(mem, old);
    free(wbuf);

    return (int)sz.cx;
}

// ─── SoftKit: medição de texto (mesma fonte/spacing do draw_text, sem repaint) ──
DX_EXPORT int dxgui_measure_text(const char* utf8, int size, int spacing) {
    if (!utf8 || size <= 0) return 0;

    int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, -1, NULL, 0);
    if (wlen <= 1) return 0;

    wchar_t* ws = (wchar_t*)malloc(sizeof(wchar_t) * wlen);
    if (!ws) return 0;

    MultiByteToWideChar(CP_UTF8, 0, utf8, -1, ws, wlen);

    int count = wlen - 1; // remove o NULL final

    HDC hdc = GetDC(NULL);
    if (!hdc) {
        free(ws);
        return count * (size / 2);
    }

    HFONT font = CreateFontW(
        -size,
        0,
        0,
        0,
        FW_NORMAL,
        FALSE,
        FALSE,
        FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE,
        L"Segoe UI"
    );

    if (!font) {
        ReleaseDC(NULL, hdc);
        free(ws);
        return count * (size / 2);
    }

    HFONT old = (HFONT)SelectObject(hdc, font);

    SIZE sz = {0, 0};
    if (count > 0) {
        GetTextExtentPoint32W(hdc, ws, count, &sz);
    }

    SelectObject(hdc, old);
    DeleteObject(font);
    ReleaseDC(NULL, hdc);
    free(ws);

    int extra = 0;
    if (count > 1) {
        extra = spacing * (count - 1);
    }

    return sz.cx + extra;
}