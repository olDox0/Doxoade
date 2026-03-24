# -*- coding: utf-8 -*-
# doxoade/tools/error_info.py

def handle_error(
    err: Exception,
    context: str = "",
    silent: bool = False,
    debug: bool = False
):
    """
    Manipulador padrão de erros do Doxoade.

    :param err: exceção capturada
    :param context: contexto da operação (ex: "carregando settings.json")
    :param silent: não exibe nada
    :param debug: exibe traceback completo
    """

    if silent:
        return

    err_type = type(err).__name__
    msg = str(err)

    prefix = "⚠️ [DOXOADE ERROR]"

    if context:
        print(f"{prefix} ({context}) -> {err_type}: {msg}")
    else:
        print(f"{prefix} {err_type}: {msg}")
        
    from traceback import print_exc
    if debug:
        print("---- TRACEBACK ----")
        print_exc()