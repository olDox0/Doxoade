// doxoade/tools/benzaiten_gui/native/dxgui_win.c
// BENZAITEN ENGINE — Windows Backend (webview edition) COM SOTERIA
//
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#define WEBVIEW_API __declspec(dllexport)
#include "include/webview.h"
#include <windows.h>
#include <string>
#include <functional>
#include <stdio.h>

// SOTERIA TAGS para diagnóstico
#define SOTERIA_BEGIN "@SOTERIA_BEGIN@\n"
#define SOTERIA_END "@SOTERIA_END@\n"
#define TAG_LEVEL "TAG_LEVEL: "
#define TAG_MOTIVO "TAG_MOTIVO: "
#define TAG_DETAIL "TAG_DETAIL: "
#define TAG_RASTRO "TAG_RASTRO_LOC: "
#define TAG_FRAME "TAG_FRAME: "

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

DX_EXPORT void* dxgui_create_window(const char* title, int width, int height, int web_mode) {
    g_web_mode = web_mode;
    
    if (web_mode) {
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
            
            // Bind do canal JS → C
            webview_bind(g_wv, "__dx_send__", [](const char* seq, const char* req, void* arg) {
                try {
                    dxgui_msg_cb cb = (dxgui_msg_cb)arg;
                    if (cb) cb(req);
                } SOTERIA_CATCH("JS_CALLBACK_CRASH", "__dx_send__ callback")
            }, (void*)g_msg_cb);
            
            webview_navigate(g_wv, "about:blank");
            return (void*)g_wv;
            
        } SOTERIA_CATCH("WINDOW_CREATE_CRASH", "dxgui_create_window")
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

DX_EXPORT void dxgui_set_ready_callback(dxgui_ready_cb cb) {
    g_ready_cb = cb;
}

DX_EXPORT void dxgui_set_click_callback(dxgui_click_cb cb) {
    g_click_cb = cb;
}

DX_EXPORT void dxgui_set_msg_callback(dxgui_msg_cb cb) {
    g_msg_cb = cb;
    // Reconfigura o bind se já estiver no modo web
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
    
    // SOTERIA: Log de entrada
    fprintf(stdout, SOTERIA_BEGIN);
    fprintf(stdout, TAG_LEVEL "INFO\n");
    fprintf(stdout, TAG_MOTIVO "EVAL_JS_ENTER\n");
    fprintf(stdout, TAG_DETAIL "dxgui_eval_js called, g_wv=%p, js=%.50s...\n", (void*)g_wv, js);
    fprintf(stdout, SOTERIA_END);
    fflush(stdout);
    
    // Cria um wrapper que executa o JS com try-catch e verifica DOM ready
    std::string wrapped_js = 
        std::string("(function() { ") +
        "try { " +
        "if (document.readyState === 'loading') { " +
        "  document.addEventListener('DOMContentLoaded', function() { " +
        "    try { " +
        std::string(js) +
        "    } catch(e) { console.error('[DXGUI Eval Error]:', e); } " +
        "  }); " +
        "} else { " +
        "  try { " +
        std::string(js) +
        "  } catch(e) { console.error('[DXGUI Eval Error]:', e); } " +
        "} " +
        "} catch(e) { console.error('[DXGUI Wrapper Error]:', e); } " +
        "})();";
    
    std::string* js_copy = new std::string(wrapped_js);
    
    // SOTERIA: Antes do dispatch
    fprintf(stdout, SOTERIA_BEGIN);
    fprintf(stdout, TAG_LEVEL "INFO\n");
    fprintf(stdout, TAG_MOTIVO "EVAL_JS_DISPATCH_START\n");
    fprintf(stdout, TAG_DETAIL "About to call webview_dispatch with wrapped JS\n");
    fprintf(stdout, SOTERIA_END);
    fflush(stdout);
    
    webview_dispatch(g_wv, [](webview_t wv, void* arg) {
        std::string* script = static_cast<std::string*>(arg);
        
        // SOTERIA: Antes do eval
        fprintf(stdout, SOTERIA_BEGIN);
        fprintf(stdout, TAG_LEVEL "INFO\n");
        fprintf(stdout, TAG_MOTIVO "EVAL_JS_EXEC_START\n");
        fprintf(stdout, TAG_DETAIL "About to call webview_eval, script=%.50s...\n", script->c_str());
        fprintf(stdout, SOTERIA_END);
        fflush(stdout);
        
        int result = webview_eval(wv, script->c_str());
        
        // SOTERIA: Após o eval
        fprintf(stdout, SOTERIA_BEGIN);
        fprintf(stdout, TAG_LEVEL "INFO\n");
        fprintf(stdout, TAG_MOTIVO "EVAL_JS_EXEC_DONE\n");
        fprintf(stdout, TAG_DETAIL "webview_eval returned %d\n", result);
        fprintf(stdout, SOTERIA_END);
        fflush(stdout);
        
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
    
    // SOTERIA: Após o dispatch
    fprintf(stdout, SOTERIA_BEGIN);
    fprintf(stdout, TAG_LEVEL "INFO\n");
    fprintf(stdout, TAG_MOTIVO "EVAL_JS_DISPATCH_DONE\n");
    fprintf(stdout, TAG_DETAIL "webview_dispatch returned\n");
    fprintf(stdout, SOTERIA_END);
    fflush(stdout);
}

DX_EXPORT int dxgui_is_ready(void) {
    return (g_wv != nullptr) ? 1 : 0;
}

DX_EXPORT void dxgui_run_loop(void) {
    if (g_web_mode && g_wv) {
        try {
            if (g_ready_cb) {
                g_ready_cb();
            }
            
            // SOTERIA: Antes do run
            fprintf(stdout, SOTERIA_BEGIN);
            fprintf(stdout, TAG_LEVEL "INFO\n");
            fprintf(stdout, TAG_MOTIVO "RUN_LOOP_START\n");
            fprintf(stdout, TAG_DETAIL "About to call webview_run\n");
            fprintf(stdout, SOTERIA_END);
            fflush(stdout);
            
            webview_run(g_wv);
            
            // SOTERIA: Após o run (só chega se fechar a janela)
            fprintf(stdout, SOTERIA_BEGIN);
            fprintf(stdout, TAG_LEVEL "INFO\n");
            fprintf(stdout, TAG_MOTIVO "RUN_LOOP_DONE\n");
            fprintf(stdout, TAG_DETAIL "webview_run finished\n");
            fprintf(stdout, SOTERIA_END);
            fflush(stdout);
            
        } SOTERIA_CATCH("RUN_LOOP_CRASH", "dxgui_run_loop")
    } else {
        // Loop GDI nativo
        MSG msg;
        while (GetMessage(&msg, NULL, 0, 0)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
    }
}