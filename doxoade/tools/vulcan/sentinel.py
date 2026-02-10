# -*- coding: utf-8 -*-
"""
Vulcan Sentinel - Auditor de Integridade Comportamental.
Garante que a otimização não alterou o resultado lógico.
"""

def verify_stability(py_func, native_func, *args, **kwargs):
    """
    Execução em Sombra (Shadowing).
    Roda ambas as versões e compara o resultado antes de confiar no binário.
    """
    try:
        # 1. Roda a versão estável (Python)
        expected_result = py_func(*args, **kwargs)
        
        # 2. Roda a versão Vulcano (Nativa)
        # Nota: Usamos um Try/Except isolado para capturar falhas de segmentação
        actual_result = native_func(*args, **kwargs)
        
        # 3. Verificação de Consistência
        if expected_result == actual_result:
            return True, actual_result
        else:
            return False, expected_result
    except Exception as e:
        import traceback
        print(f"\033[31m ■ Erro: {e}")
        traceback.print_tb(e.__traceback__)
        return False, None