# alfagold/core/math_utils.py
import numpy as np
try:
    from .math_lut import LUT
except ImportError:
    LUT = None

def softmax(x):
    """
    Função Softmax otimizada via LUT.
    """
    # Shift para estabilidade (x - max)
    # Mantém float32
    shift_x = x - np.max(x, axis=-1, keepdims=True)
    
    if LUT:
        # Usa tabela interpolada (Muito rápido)
        e_x = LUT.exp(shift_x)
    else:
        # Fallback NumPy puro
        e_x = np.exp(shift_x)
        
    return e_x / np.sum(e_x, axis=-1, keepdims=True)

def gelu(x):
    """GELU com fallback otimizado."""
    if LUT:
        return LUT.gelu(x)
    
    # Fallback Micro-otimizado (x*x*x em vez de pow)
    # Constantes
    S2PI = 0.7978845608 # sqrt(2/pi)
    COEF = 0.044715
    
    inner = S2PI * (x + COEF * (x * x * x))
    return 0.5 * x * (1 + np.tanh(inner))

def d_gelu(x):
    """Derivada GELU."""
    if LUT:
        return LUT.d_gelu(x)
        
    # Fallback Analítico
    S2PI = 0.7978845608
    COEF = 0.044715
    x3 = x * x * x
    
    tanh_inner = np.tanh(S2PI * (x + COEF * x3))
    
    cdf = 0.5 * (1 + tanh_inner)
    pdf = np.exp(-0.5 * x * x) * (1.0 / 2.5066282746) # 1/sqrt(2pi)
    
    return cdf + x * pdf