# doxoade/doxoade/diagnostic/check_exame_clone.py
import logging
try:
    from .check_exame import funcao_complexa
except ImportError as e:
    logging.error(f' Ocorrencia no check_exame_clone: {e}')
    from check_exame import funcao_complexa

def disparar_erro_de_assinatura():
    return funcao_complexa()