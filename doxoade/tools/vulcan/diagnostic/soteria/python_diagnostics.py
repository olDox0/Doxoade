# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/python_diagnostics.py
import re
from .crash_signatures import PYTHON_EXCEPTIONS, get_tactical_advice

PYTHON_EXCEPTIONS.update({
    "RecursionError": ("Estouro de Córtex", "O sistema entrou em um loop infinito de chamadas (Recursividade Máxima)."),
    "ImportError": ("Falha de Enlace", "Um módulo nativo (Tier 1) foi localizado, mas não pôde ser carregado por falta de dependências C."),
    "OSError": ("Bloqueio de Sistema", "Falha de baixo nível no Windows (Arquivo travado ou Permissão negada).")
})

def diagnose_python_error(exc_type: str, message: str) -> tuple:
    """Especialista em escavação de lógica Python."""
    status, explanation = PYTHON_EXCEPTIONS.get(exc_type, (exc_type, message))
    msg_low = message.lower()
#    status = exc_type
#    explanation = message

    if exc_type in PYTHON_EXCEPTIONS:
        status, base_expl = PYTHON_EXCEPTIONS[exc_type]
        explanation = f"{base_expl} ({message})"

    # --- Lógica de Precisão: UnboundLocalError ---
    if exc_type == "UnboundLocalError":
        var = re.search(r"variable '(.+?)'", message)
        if var:
            explanation = f"A variável '{var.group(1)}' é local, mas foi lida antes da atribuição. Verifique se falta 'global'."
            
    if "maximum recursion depth exceeded" in message.lower():
        status = "Loop Infinito"
        explanation = "Estouro de Córtex: Uma função está chamando a si mesma sem parar."

    if "access violation" in msg_low:
        status = "Access Violation (Hardware)"
        explanation = "Violação de Memória: O script tentou acessar uma coordenada física proibida na RAM."
        # Se detectarmos escrita no endereço ZERO, o laudo fica mais agressivo
        if "0x00000000" in msg_low or "writing 0x0" in msg_low:
             explanation = "NullPointerDereference: Tentativa de escrita no endereço ZERO. Ponteiro não inicializado."
    
    elif "stack overflow" in msg_low:
        status = "StackOverflow"
        explanation = "Estouro de Pilha: A memória de execução foi exaurida por recursão ou alocação excessiva."

    # --- Lógica de Precisão: AttributeError ---
    if exc_type == "AttributeError":
        explanation = "O código tentou acessar algo que não existe no objeto. Verifique se o nome está correto ou se o objeto é 'None'."

    advice = get_tactical_advice(exc_type, message)
    if advice:
        explanation += f"\n\n\x1b[1;33m💡 INSIGHT TÁTICO:\x1b[0m\n{advice}"
        
    return status, explanation
    
def get_tactical_advice(exc_type, message):
    # ... (lógica anterior) ...
    if exc_type == "RecursionError":
        return "RECOMENDAÇÃO: Verifique se há funções chamando a si mesmas sem critério de parada ou se o orquestrador entrou em loop circular."
    if "DLL load failed" in message:
        return "RECOMENDAÇÃO: O binário nativo exige o Runtime do Visual C++ ou MinGW. Verifique se o w64devkit está no PATH."
    return None