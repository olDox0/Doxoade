# doxoade/doxoade/tools/horus.py
import functools
# [DOX-UNUSED] import json
import time
# [DOX-UNUSED] import os
from .telemetry_tools.logger import chief_heartbeat

def horus_trace(func):
    """
    Shadow Trace v1.1 - Platinum Observer.
    Captura o ciclo de vida completo da função para o banco Hades.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Nome qualificado para facilitar a busca
        func_name = f"{func.__name__}"
        
        # Combina args e kwargs de forma inteligível para a chave 'args' consumida pelo view
        combined_args = f"args={args}" if args else ""
        if kwargs:
            combined_args += f" kwargs={kwargs}" if combined_args else f"kwargs={kwargs}"
        if not combined_args:
            combined_args = "()"
        
        # Injetamos o rastro de entrada utilizando a chave correta 'args'
        chief_heartbeat("HORUS", "FUNCTION_IN", {
            "func": func_name,
            "args": combined_args[:200]  # Captura tática
        })
        
        t0 = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            ms = (time.perf_counter() - t0) * 1000
            
            # Registro de saída bem-sucedida
            chief_heartbeat("HORUS", "FUNCTION_OUT", {
                "func": func_name,
                "output": str(result)[:200],
                "ms": round(ms, 2)
            })
            return result
        except Exception as e:
            # Captura o erro no nível funcional antes de subir
            chief_heartbeat("HORUS", "FUNCTION_ERROR", {
                "func": func_name,
                "error": str(e)
            })
            raise e
    return wrapper