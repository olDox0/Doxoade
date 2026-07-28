# doxoade/tools/benzaiten_gui/hermes_router.py
# -*- coding: utf-8 -*-
"""
Hermes Router — Camada de Mensageria Genérica para o Benzaiten.
Transforma a DLL C (dxgui) em uma API de ações assíncronas via JSON.
Qualquer projeto Doxoade pode usar este router para comunicar com o WebView2.
"""
import json
import logging
import traceback

class HermesRouter:
    """
    Roteador de mensagens JS <-> Python.
    Uso:
        win = BenzaitenWindow("App", mode="web")
        router = HermesRouter(win)
        router.register_action("minha_acao", minha_funcao_python)
    """
    def __init__(self, window):
        self.window = window
        self._handlers = {}
        
        # Conecta o callback nativo da DLL C ao nosso router
        self.window.on_message(self._handle_raw_message)
        logging.info("[HERMES] Router inicializado e escutando __dx_send__.")

    def register_action(self, action_name: str, handler: callable):
        """Registra uma função Python para responder a uma ação do JS."""
        self._handlers[action_name] = handler
        logging.info(f"[HERMES] Ação '{action_name}' registrada.")

    def _handle_raw_message(self, raw_msg):
        """
        Callback cru vindo da DLL C (webview_bind).
        Roda na thread da UI. Parseia o JSON e despacha.
        """
        try:
            #  CORREÇÃO: A mensagem pode vir como string OU bytes
            if isinstance(raw_msg, bytes):
                msg_str = raw_msg.decode('utf-8')
            elif isinstance(raw_msg, str):
                msg_str = raw_msg
            else:
                # Fallback: converte qualquer coisa para string
                msg_str = str(raw_msg)
            
            # Remove aspas extras se houver (JSON dentro de string)
            msg_str = msg_str.strip('"').strip("'")
            
            request = json.loads(msg_str)
        except Exception as e:
            logging.error(f"[HERMES] Falha ao parsear mensagem JS: {e} | Raw: {raw_msg}")
            return

        req_id = request.get("id", "unknown")
        action = request.get("action")
        payload = request.get("payload", {})

        if action not in self._handlers:
            self._send_response(req_id, "error", {"message": f"Ação desconhecida: {action}"})
            return

        # Executa o handler Python
        try:
            result = self._handlers[action](payload)
            self._send_response(req_id, "success", result or {})
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"[HERMES] Erro no handler '{action}': {tb}")
            self._send_response(req_id, "error", {"message": str(e)})


    def _send_response(self, req_id: str, status: str, payload: dict):
        """Empacota a resposta e injeta no JavaScript via eval_js."""
        response = {
            "id": req_id,
            "status": status,
            "payload": payload
        }
        
        # Serializa para JSON
        json_str = json.dumps(response, ensure_ascii=False)
        
        # Escapa aspas para injeção segura na string JS
        safe_json = json_str.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        
        # Injeta no JS chamando a função global __dx_receive__
        js_code = f"window.__dx_receive__('{safe_json}');"
        self.window.eval_js(js_code)