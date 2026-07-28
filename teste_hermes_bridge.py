# teste_hermes_bridge.py
import sys
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from doxoade.tools.benzaiten_gui.core import BenzaitenWindow
from doxoade.tools.benzaiten_gui.hermes_router import HermesRouter

# --- Handlers Python ---
def handle_ping(payload):
    print(f"[PYTHON] Recebi PING com payload: {payload}")
    return {"msg": "PONG do Python!", "echo": payload.get("msg")}

def handle_sum(payload):
    a = payload.get("a", 0)
    b = payload.get("b", 0)
    return {"result": a + b}

# --- Setup ---
print("🚀 Iniciando Teste da Ponte Hermes...")
win = BenzaitenWindow("Hermes Bridge Test", 800, 600, mode="web")
router = HermesRouter(win)
router.register_action("ping", handle_ping)
router.register_action("sum", handle_sum)

html_base = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Hermes Test</title>
<style>
    body { font-family: sans-serif; background: #1e1e2e; color: #cdd6f4; padding: 40px; text-align: center; }
    button { padding: 12px 24px; margin: 8px; cursor: pointer; background: #89b4fa; color: #1e1e2e;
             border: none; border-radius: 8px; font-weight: bold; }
    button:hover { background: #b4befe; }
    #log { margin-top: 20px; background: #11111b; padding: 15px; border-radius: 8px;
           font-family: monospace; text-align: left; max-height: 300px; overflow-y: auto; }
    .ok { color: #a6e3a1; } .err { color: #f38ba8; } .info { color: #89b4fa; }
    #eval-status { margin-top: 15px; padding: 10px; border-radius: 6px; background: #313244; }
</style>
</head>
<body>
    <h2>🪽 Ponte Hermes (JS ↔ Python)</h2>
    <div id="eval-status">⏳ Aguardando eval do Python...</div>
    <button onclick="testPing()">🏓 PING</button>
    <button onclick="testSum()">🔢 SUM (5+7)</button>
    <button onclick="testEvalResponse()">📡 Pedir Eval ao Python</button>
    <div id="log"></div>

    <script>
        window.__dx_requests__ = {};
        let __req_counter__ = 0;

        window.__dx_receive__ = function(json_str) {
            try {
                const r = JSON.parse(json_str);
                log('✅ Resposta Python: ' + JSON.stringify(r), 'ok');
                if (window.__dx_requests__[r.id]) {
                    if (r.status === 'success') window.__dx_requests__[r.id].resolve(r.payload);
                    else window.__dx_requests__[r.id].reject(r.payload);
                    delete window.__dx_requests__[r.id];
                }
            } catch(e) { log('❌ Erro parse: ' + e.message, 'err'); }
        };

        window.dx_send = function(action, payload = {}) {
            return new Promise((resolve, reject) => {
                const req_id = 'req_' + (++__req_counter__);
                window.__dx_requests__[req_id] = { resolve, reject };
                log('➡️ Enviando: ' + action, 'info');
                window.__dx_send__(JSON.stringify({ id: req_id, action, payload }));
            });
        };

        // Função global que o Python pode chamar via eval_js
        window.__python_eval_callback__ = function(result) {
            const el = document.getElementById('eval-status');
            el.innerHTML = '✅ Eval do Python recebido: <b>' + result + '</b>';
            el.style.background = '#1e3a1e';
            el.style.color = '#a6e3a1';
            log('📨 Eval callback: ' + result, 'ok');
        };

        function log(msg, cls) {
            const d = document.getElementById('log');
            d.innerHTML += '<div class="' + (cls||'') + '">[' +
                new Date().toLocaleTimeString() + '] ' + msg + '</div>';
            d.scrollTop = d.scrollHeight;
        }

        async function testPing() {
            const r = await window.dx_send("ping", { msg: "Olá do WebView2!" });
            log('Ping: ' + JSON.stringify(r), 'ok');
        }
        async function testSum() {
            const r = await window.dx_send("sum", { a: 5, b: 7 });
            log('Sum: ' + JSON.stringify(r), 'ok');
        }
        function testEvalResponse() {
            log('📡 Pedindo ao Python para chamar eval_js...', 'info');
            window.dx_send("request_eval", {});
        }

        log('🚀 Bridge JS inicializada', 'ok');
    </script>
</body>
</html>
"""

# 🔥 CORREÇÃO CRÍTICA: eval_js DEPOIS do load_html, com delay para o DOM
@win.on_ready
def _pronto():
    print("[PYTHON] WebView pronto. Injetando HTML...")
    win.load_html(html_base)

    # Aguarda o DOM carregar antes de executar eval
    # O webview_dispatch processa em ordem, então este dispatch
    # será executado DEPOIS do set_html
    import time
    def _delayed_eval():
        time.sleep(0.5)  # Garante que o DOM está pronto
        win.eval_js("""
            (function() {
                if (typeof window.__python_eval_callback__ === 'function') {
                    window.__python_eval_callback__('eval_js funcionando! 🎉');
                }
                document.body.style.borderTop = '4px solid #a6e3a1';
                return 'eval_ok';
            })();
        """)
        print("[PYTHON] eval_js executado após load_html")

    import threading
    threading.Thread(target=_delayed_eval, daemon=True).start()

print("🏃 Rodando loop da GUI...")
win.run()