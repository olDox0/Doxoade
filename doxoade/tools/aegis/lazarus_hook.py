# -*- coding: utf-8 -*-
# doxoade/tools/aegis/lazarus_hook.py
import sys
import traceback

def lazarus_excepthook(etype, value, tb):
    if issubclass(etype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(etype, value, tb)
        return

    import os
    # Se estivermos em um subprocesso capturado (VULCAN_META_DEBUG ou similar)
    # Apenas despeja o erro para o pai capturar
    is_captured = os.environ.get('DOXOADE_AUTHORIZED_RUN') == '1'

    try:
        from doxoade.rescue import activate_protocol
        error_data = "".join(traceback.format_exception(etype, value, tb))
        
        if is_captured:
            # Não abre o menu, apenas garante que o rastro saia limpo
            sys.stderr.write(error_data)
        else:
            activate_protocol(error_data)
    except Exception:
        sys.__excepthook__(etype, value, tb)

def install():
    sys.excepthook = lazarus_excepthook