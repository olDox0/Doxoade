# doxoade/diagnostic/check_exame_clone.py
import logging

# Se o diagnóstico roda na pasta 'diagnostic', o import relativo deve funcionar
try:
    from .check_exame import funcao_complexa
except ImportError as e:
    logging.error(f" Ocorrencia no check_exame_clone: {e}")
    # Fallback para execução direta
    from check_exame import funcao_complexa

def disparar_erro_de_assinatura():
    # Passar 0 argumentos para uma função que exige 1 ('a')
    return funcao_complexa()