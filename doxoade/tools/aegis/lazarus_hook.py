# -*- coding: utf-8 -*-
# doxoade/tools/aegis/lazarus_hook.py
import sys
import os

def lazarus_crash_handler(etype, value, tb):
    """Captura falhas fatais que o try/except normal não pegou."""
    import traceback
    
    if "maximum recursion depth" in str(value):
        # Se for recursão, o sistema de resgate padrão não pode ser usado
        # pois ele dispararia mais recursão. Fazemos um dump bruto.
        print("\x1b[31m[!] ERRO DE RECURSÃO NO MOTOR. BLOQUEANDO VIGILÂNCIA.\x1b[0m")
        return 
        
    error_data = "".join(traceback.format_exception(etype, value, tb))
    
    # Grava um log de emergência em texto puro (sem cores, sem frescura)
    # caso o sistema de UI esteja quebrado.
    with open("FATAL_CRASH_DUMP.txt", "w", encoding="utf-8") as f:
        f.write(error_data)
        
    print("\n\x1b[41;1m 🔥 CRASH FATAL DETECTADO \x1b[0m")
    print(f"Evidência salva em: {os.path.abspath('FATAL_CRASH_DUMP.txt')}")
    
    # Tenta acionar o Lazarus se ele estiver importável
    try:
        from doxoade.rescue import activate_protocol
        activate_protocol(error_data)
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] lazarus_crash_handler: {e}")
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

def install_shield():
    sys.excepthook = lazarus_crash_handler