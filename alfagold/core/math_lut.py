# alfagold/core/math_lut.py
import numpy as np

class MathLUT:
    """
    Lookup Table v2.1 (Lazy Loading).
    Otimizada para não impactar o tempo de inicialização da CLI.
    As tabelas só são geradas na primeira chamada de cálculo.
    """
    def __init__(self, resolution=65536, range_min=-10.0, range_max=10.0):
        # Configuração leve (apenas escalares)
        self.min = float(range_min)
        self.max = float(range_max)
        self.resolution = resolution
        
        # Constantes de passo
        self.step = (range_max - range_min) / (resolution - 1)
        self.inv_step = 1.0 / self.step
        
        # Estado de prontidão
        self._ready = False
        
        # Placeholders
        self.gelu_table = None
        self.d_gelu_table = None
        self.exp_table = None

    def _lazy_init(self):
        """Gera as tabelas pesadas apenas quando necessário."""
        if self._ready: return
        
        # print(f"   ⚡ [MathLUT] Gerando tabelas interpoladas ({self.resolution} pts)...")
        # (Comentamos o print para ser silencioso em produção ou usamos logger se preferir)
        
        x = np.linspace(self.min, self.max, self.resolution).astype(np.float32)
        
        # 1. GELU
        SQRT_2_OVER_PI = np.sqrt(2 / np.pi).astype(np.float32)
        COEF = 0.044715
        inner = SQRT_2_OVER_PI * (x + COEF * (x * x * x))
        self.gelu_table = 0.5 * x * (1 + np.tanh(inner))
        
        # 2. Derivada GELU
        self.d_gelu_table = np.gradient(self.gelu_table, self.step)
        
        # 3. EXP
        self.exp_table = np.exp(x)
        
        self._ready = True

    def _lookup_interpolated(self, x, table_name):
        # Gatilho Lazy: Se não estiver pronto, prepara agora
        if not self._ready: self._lazy_init()
        
        # Seleciona a tabela correta
        if table_name == 'gelu': table = self.gelu_table
        elif table_name == 'd_gelu': table = self.d_gelu_table
        elif table_name == 'exp': table = self.exp_table
        else: return x # Fallback
        
        # Lógica de Interpolação
        x_idx = (x - self.min) * self.inv_step
        idx_i = np.floor(x_idx).astype(np.int32)
        idx_i = np.clip(idx_i, 0, self.resolution - 2)
        
        t = x_idx - idx_i
        t = np.clip(t, 0.0, 1.0)
        
        y0 = table[idx_i]
        y1 = table[idx_i + 1]
        
        return y0 + t * (y1 - y0)

    def gelu(self, x):
        return self._lookup_interpolated(x, 'gelu')

    def d_gelu(self, x):
        return self._lookup_interpolated(x, 'd_gelu')
    
    def exp(self, x):
        return self._lookup_interpolated(x, 'exp')

# Instância Global Leve
try:
    LUT = MathLUT()
except Exception as e:
    # Fallback silencioso
    LUT = None