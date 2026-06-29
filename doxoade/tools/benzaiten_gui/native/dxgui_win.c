// doxoade/tools/benzaiten_gui/native/dxgui_win.c
//
// BENZAITEN ENGINE — Windows Backend (webview/webview edition)
//
// Usa a lib webview (https://github.com/webview/webview) que encapsula
// WebView2 com uma API C pura e estável, sem VTables manuais.
//
// Compilação (via doxoade gui build):
//   g++ -shared -O2 -std=c++17 -o dxgui.dll dxgui_win.c \
//       -DWEBVIEW_API=__declspec(dllexport)               \
//       -mwindows -lole32 -loleaut32 -luuid -lshlwapi     \
//       -L.doxoade/benzaiten -lWebView2Loader
//
// IMPORTANTE: webview.h deve estar em native/include/webview.h
// Baixe em: https://raw.githubusercontent.com/webview/webview/master/webview.h
//
// Dependência em runtime: WebView2Loader.dll (baixada por doxoade gui fetch-deps)

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE

// webview.h é C++ — compilamos este arquivo com g++ (não gcc)
// A API externa é C pura via extern "C" + __declspec(dllexport)
#define WEBVIEW_API __declspec(dllexport)
#include "include/webview.h"

#include <windows.h>
#include <string>
#include <functional>

#define DX_EXPORT extern "C" __declspec(dllexport)

// ─── Estado global ────────────────────────────────────────────────────────────
typedef void (*dxgui_ready_cb)(void);
typedef void (*dxgui_click_cb)(int x, int y);
typedef void (*dxgui_msg_cb)(const char* msg);

static webview_t   g_wv        = nullptr;
static int         g_web_mode  = 0;
static dxgui_ready_cb g_ready_cb = nullptr;
static dxgui_msg_cb   g_msg_cb   = nullptr;
static dxgui_click_cb g_click_cb = nullptr;

// HTML pendente (chamado antes do ready)
static std::string g_pending_html;
static std::string g_pending_url;

// ─── API pública ──────────────────────────────────────────────────────────────

DX_EXPORT void* dxgui_create_window(const char* title, int width, int height, int web_mode) {
    g_web_mode = web_mode;

    if (web_mode) {
        // webview_create(debug=0, window=nullptr) cria uma janela própria gerenciada
        g_wv = webview_create(0, nullptr);
        if (!g_wv) return nullptr;

        webview_set_title(g_wv, title);
        webview_set_size(g_wv, width, height, WEBVIEW_HINT_NONE);

        // Expõe canal JS → C: window.__dx_send__("mensagem")
        webview_bind(g_wv, "__dx_send__", [](const char* seq, const char* req, void* arg) {
            dxgui_msg_cb cb = (dxgui_msg_cb)arg;
            if (cb) cb(req);
        }, (void*)g_msg_cb);

        // Navega para blank primeiro; HTML real é carregado via dxgui_load_html
        webview_navigate(g_wv, "about:blank");

        return (void*)g_wv;
    } else {
        // Modo native: janela GDI simples (código original mantido)
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
}

DX_EXPORT void dxgui_set_ready_callback(dxgui_ready_cb cb) {
    g_ready_cb = cb;
}

DX_EXPORT void dxgui_set_click_callback(dxgui_click_cb cb) {
    g_click_cb = cb;
}

DX_EXPORT void dxgui_set_msg_callback(dxgui_msg_cb cb) {
    g_msg_cb = cb;
}

DX_EXPORT void dxgui_navigate(void* handle, const char* url) {
    if (!g_wv || !url) return;
    // webview_dispatch garante execução no thread do webview
    std::string url_copy(url);
    webview_dispatch(g_wv, [](webview_t wv, void* arg) {
        std::string* s = (std::string*)arg;
        webview_navigate(wv, s->c_str());
        delete s;
    }, new std::string(url_copy));
}

DX_EXPORT void dxgui_load_html(void* handle, const char* html) {
    if (!g_wv || !html) return;
    std::string html_copy(html);
    webview_dispatch(g_wv, [](webview_t wv, void* arg) {
        std::string* s = (std::string*)arg;
        webview_set_html(wv, s->c_str());
        delete s;
    }, new std::string(html_copy));
}

DX_EXPORT void dxgui_eval_js(void* handle, const char* js) {
    if (!g_wv || !js) return;
    std::string js_copy(js);
    webview_dispatch(g_wv, [](webview_t wv, void* arg) {
        std::string* s = (std::string*)arg;
        webview_eval(wv, s->c_str());
        delete s;
    }, new std::string(js_copy));
}

DX_EXPORT int dxgui_is_ready(void) {
    return (g_wv != nullptr) ? 1 : 0;
}

DX_EXPORT void dxgui_run_loop(void) {
    if (g_web_mode && g_wv) {
        // Dispara ready_cb antes do loop (webview já está inicializado aqui)
        if (g_ready_cb) g_ready_cb();
        webview_run(g_wv);
        webview_destroy(g_wv);
        g_wv = nullptr;
    } else {
        // Modo native: loop Win32 simples
        MSG msg = {};
        while (GetMessage(&msg, nullptr, 0, 0)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
    }
}