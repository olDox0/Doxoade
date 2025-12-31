# alfagold/core/math_utils.py
import numpy as np

def softmax(x):
    """
    Função Softmax estável numericamente.
    Converte logits em probabilidades.
    """
    # Subtrai o max para evitar overflow exponencial (shift invariance)
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)

def gelu(x):
    """
    Gaussian Error Linear Unit (Ativação moderna para Transformers).
    Aproximação: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
    """
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * np.power(x, 3))))

def d_gelu(x):
    """
    Derivada da GELU (para Backpropagation).
    """
    cdf = 0.5 * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * np.power(x, 3))))
    pdf = np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
    return cdf + x * pdf