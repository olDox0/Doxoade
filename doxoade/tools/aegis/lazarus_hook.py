# -*- coding: utf-8 -*-
# doxoade/tools/aegis/lazarus_hook.py
import sys
import traceback

def lazarus_excepthook(etype, value, tb):
    if issubclass(etype, KeyboardInterrupt):
        sys.__excepthook__(etype, value, tb)
        return

    import os
    is_captured = os.environ.get('DOXOADE_AUTHORIZED_RUN') == '1'
    
    # --- [ CAPTURA DE PRECISÃO ] ---
    # Se for um SystemExit (como sinais do SO ou sys.exit(n)), pegamos o código real
    exit_code = 1
    if issubclass(etype, SystemExit):
        exit_code = value.code if isinstance(value.code, int) else (1 if value.code else 0)

    try:
        from doxoade.rescue import activate_protocol
        import traceback
        error_data = "".join(traceback.format_exception(etype, value, tb))
        
        if is_captured:
            sys.stderr.write(error_data)
        else:
            # FIX: Agora passamos o exit_code capturado para o resgate
            activate_protocol(error_data, exit_code=exit_code)
    except Exception:
        sys.__excepthook__(etype, value, tb)

def install():
    sys.excepthook = lazarus_excepthook