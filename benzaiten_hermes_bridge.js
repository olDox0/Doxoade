// benzaiten_hermes_bridge.js
// O "Driver" de comunicação do Frontend.

window.__dx_requests__ = {};
let __req_counter__ = 0;

// 1. Função global chamada pelo Python (via eval_js)
window.__dx_receive__ = function(json_str) {
    try {
        const response = JSON.parse(json_str);
        const req_id = response.id;
        
        if (window.__dx_requests__[req_id]) {
            if (response.status === 'success') {
                window.__dx_requests__[req_id].resolve(response.payload);
            } else {
                window.__dx_requests__[req_id].reject(response.payload);
            }
            // Limpa a memória
            delete window.__dx_requests__[req_id];
        }
    } catch (e) {
        console.error("[HERMES JS] Erro ao processar resposta:", e);
    }
};

// 2. Função pública para o JS chamar o Python
window.dx_send = function(action, payload = {}) {
    return new Promise((resolve, reject) => {
        const req_id = 'req_' + (++__req_counter__);
        
        // Guarda a Promise pendente
        window.__dx_requests__[req_id] = { resolve, reject };
        
        // Empacota e envia via bind nativo do WebView2
        const request = JSON.stringify({ 
            id: req_id, 
            action: action, 
            payload: payload 
        });
        
        // __dx_send__ é a função mágica exposta pela DLL C (webview_bind)
        window.__dx_send__(request); 
    });
};