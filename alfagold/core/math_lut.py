# alfagold/core/math_lut.py
import numpy as np

class MathLUT:
    """
    Lookup Table para funções de ativação pesadas.
    Troca precisão infinita por velocidade extrema (Cache L1/L2).
    """
    def __init__(self, resolution=100000, range_min=-10.0, range_max=10.0):
        self.min = range_min
        self.max = range_max
        self.scale = resolution / (range_max - range_min)
        self.resolution = resolution
        
        # Gera o domínio X
        x = np.linspace(range_min, range_max, resolution).astype(np.float32)
        
        # Pré-calcula GELU
        # 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
        cdf = 0.5 * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * np.power(x, 3))))
        self.gelu_table = x * cdf
        
        # Pré-calcula Derivada GELU (aproximada)
        pdf = np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
        self.d_gelu_table = cdf + x * pdf
        
        # Pré-calcula EXP (para Softmax)
        # Clipamos em -60 a 60 para evitar overflow
        self.exp_table = np.exp(x)

        print(f"   ⚡ [MathLUT] Tabelas carregadas na RAM ({resolution} pontos).")

    def gelu(self, x):
        """Busca rápida (Vetorizada)."""
        # Mapeia x para índices da tabela
        # Clip para garantir que fique dentro do range pré-calculado
        idx = (x - self.min) * self.scale
        idx = np.clip(idx, 0, self.resolution - 1).astype(np.int32)
        return self.gelu_table[idx]

    def d_gelu(self, x):
        idx = (x - self.min) * self.scale
        idx = np.clip(idx, 0, self.resolution - 1).astype(np.int32)
        return self.d_gelu_table[idx]

# Instância Global (Singleton)
# Inicializa apenas quando importado
LUT = MathLUT()