import os

CORE_CONTENT = r'''"""
DOXONET CORE v6.1 (JIT Syntax Fix).
Correção: Desempacotamento explícito no get_state.
"""
import numpy as np
import re
import pickle
import os
from .accelerator import jit, status

# Evita print no import para não sujar CLI, mas mantém status acessível
# print(f"   [CORE] Backend: {status()}")

# --- KERNELS MATEMÁTICOS (ESTÁTICOS & COMPILÁVEIS) ---

@jit
def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.minimum(np.maximum(x, -60.0), 60.0)))

@jit
def _dtanh(y):
    return 1.0 - y * y

@jit
def _dsigmoid(y):
    return y * (1.0 - y)

@jit
def _lstm_forward_jit(inputs, h_init, c_init, Wf, Wi, Wc, Wo, Wy, bf, bi, bc, bo, by):
    T, _ = inputs.shape
    H = h_init.shape[1]
    O = by.shape[1]
    
    outputs = np.zeros((T, O), dtype=np.float32)
    
    cache_gates = np.zeros((T, 4, H), dtype=np.float32)
    cache_h = np.zeros((T, H), dtype=np.float32)
    cache_c = np.zeros((T, H), dtype=np.float32)
    cache_concat = np.zeros((T, inputs.shape[1] + H), dtype=np.float32)
    
    h = h_init
    c = c_init
    
    for t in range(T):
        x = inputs[t:t+1]
        concat = np.hstack((x, h))
        cache_concat[t] = concat
        
        f = _sigmoid(np.dot(concat, Wf) + bf)
        i = _sigmoid(np.dot(concat, Wi) + bi)
        c_bar = np.tanh(np.dot(concat, Wc) + bc)
        o = _sigmoid(np.dot(concat, Wo) + bo)
        
        c = f * c + i * c_bar
        h = o * np.tanh(c)
        y = np.dot(h, Wy) + by
        
        outputs[t] = y
        cache_h[t] = h
        cache_c[t] = c
        cache_gates[t, 0] = f
        cache_gates[t, 1] = i
        cache_gates[t, 2] = c_bar
        cache_gates[t, 3] = o
        
    return outputs, h, c, cache_concat, cache_h, cache_c, cache_gates

@jit
def _lstm_backward_jit(dY, cache_concat, cache_h, cache_c, cache_gates, 
                       Wf, Wi, Wc, Wo, Wy, h_init, c_init):
    T = dY.shape[0]
    I = cache_concat.shape[1] - cache_h.shape[1]
    H = cache_h.shape[1]
    O = Wy.shape[1]
    
    dWf = np.zeros_like(Wf); dWi = np.zeros_like(Wi)
    dWc = np.zeros_like(Wc); dWo = np.zeros_like(Wo); dWy = np.zeros_like(Wy)
    dbf = np.zeros((1, H), dtype=np.float32); dbi = np.zeros((1, H), dtype=np.float32)
    dbc = np.zeros((1, H), dtype=np.float32); dbo = np.zeros((1, H), dtype=np.float32)
    dby = np.zeros((1, O), dtype=np.float32)
    
    dInputs = np.zeros((T, I), dtype=np.float32)
    dh_next = np.zeros((1, H), dtype=np.float32)
    dc_next = np.zeros((1, H), dtype=np.float32)
    
    for t in range(T - 1, -1, -1):
        dy = dY[t:t+1]
        concat = cache_concat[t:t+1]
        h_curr = cache_h[t:t+1]
        c_curr = cache_c[t:t+1]
        
        if t > 0: c_prev = cache_c[t-1:t]
        else: c_prev = c_init
            
        f = cache_gates[t, 0:1]; i = cache_gates[t, 1:2]
        c_bar = cache_gates[t, 2:3]; o = cache_gates[t, 3:4]
        
        dWy += np.dot(h_curr.T, dy)
        dby += dy
        
        dh = np.dot(dy, Wy.T) + dh_next
        
        do = dh * np.tanh(c_curr)
        do_raw = _dsigmoid(o) * do
        dc = dc_next + (dh * o * _dtanh(np.tanh(c_curr)))
        
        dc_bar = dc * i
        dc_bar_raw = _dtanh(c_bar) * dc_bar
        di = dc * c_bar
        di_raw = _dsigmoid(i) * di
        df = dc * c_prev
        df_raw = _dsigmoid(f) * df
        
        dc_next = dc * f
        
        dWo += np.dot(concat.T, do_raw); dbo += do_raw
        dWc += np.dot(concat.T, dc_bar_raw); dbc += dc_bar_raw
        dWi += np.dot(concat.T, di_raw); dbi += di_raw
        dWf += np.dot(concat.T, df_raw); dbf += df_raw
        
        d_concat = (np.dot(do_raw, Wo.T) + np.dot(dc_bar_raw, Wc.T) + 
                    np.dot(di_raw, Wi.T) + np.dot(df_raw, Wf.T))
        
        dInputs[t] = d_concat[0, :I]
        dh_next = d_concat[0, I:]
        
    return dInputs, dWf, dWi, dWc, dWo, dWy, dbf, dbi, dbc, dbo, dby

@jit
def _adam_update(param, grad, m, v, t, lr, beta1, beta2, eps):
    m[:] = beta1 * m + (1.0 - beta1) * grad
    v[:] = beta2 * v + (1.0 - beta2) * (grad ** 2)
    m_hat = m / (1.0 - beta1 ** t)
    v_hat = v / (1.0 - beta2 ** t)
    param[:] -= lr * m_hat / (np.sqrt(v_hat) + eps)

# --- CLASSES WRAPPER ---

def softmax(x):
    x_safe = np.nan_to_num(x)
    x_safe = np.clip(x_safe, -60, 60)
    e_x = np.exp(x_safe - np.max(x_safe, axis=1, keepdims=True))
    return e_x / (e_x.sum(axis=1, keepdims=True) + 1e-8)

def quantize(weights):
    weights = np.nan_to_num(weights)
    max_val = np.max(np.abs(weights))
    if max_val == 0: return weights.astype(np.int8), 1.0
    scale = max_val / 127.0
    q_weights = np.round(weights / scale).astype(np.int8)
    return q_weights, scale

def dequantize(q_weights, scale):
    return q_weights.astype(np.float32) * scale

class Tokenizer:
    def __init__(self):
        self.vocabulario = {}; self.inverso = {}; self.contador = 0
        self.adicionar_token("<PAD>"); self.adicionar_token("<UNK>"); self.adicionar_token("ENDMARKER")
    
    def adicionar_token(self, token):
        if token not in self.vocabulario:
            self.vocabulario[token] = self.contador
            self.inverso[self.contador] = token
            self.contador += 1
            
    def treinar(self, textos):
        for texto in textos:
            for t in self._quebrar(texto): self.adicionar_token(t)

    def _quebrar(self, texto):
        return re.findall(r"[\w]+|[=+\-*/(){}:\[\]<>,.!]", texto)

    def converter_para_ids(self, texto):
        tokens = self._quebrar(texto)
        return np.array([self.vocabulario.get(t, 1) for t in tokens], dtype=np.int32)

class CamadaEmbedding:
    def __init__(self, V, D):
        self.E = np.random.randn(V, D).astype(np.float32) * 0.1
        self.grad_buffer = np.zeros_like(self.E); self.m = np.zeros_like(self.E); self.v = np.zeros_like(self.E); self.t = 0
        self.ultimo_input = None

    def forward(self, ids):
        self.ultimo_input = ids
        return self.E[ids]

    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY)
        np.add.at(self.grad_buffer, self.ultimo_input, dY)

    def apply_update(self, lr, batch_size=1):
        self.t += 1
        _adam_update(self.E, self.grad_buffer, self.m, self.v, self.t, lr, 0.9, 0.999, 1e-7)
        self.grad_buffer.fill(0)
    
    def get_state(self):
        q, s = quantize(self.E)
        return {'q_E': q, 's_E': s}

    def load_state(self, s): 
        self.E = dequantize(s['q_E'], s['s_E']); self.m.fill(0); self.v.fill(0)

class LSTM:
    def __init__(self, I, H, O):
        self.I, self.H, self.O = I, H, O
        std = np.float32(1.0 / np.sqrt(H))
        
        self.params = {}
        for k in ['Wf', 'Wi', 'Wc', 'Wo']: self.params[k] = np.random.uniform(-std, std, (I + H, H)).astype(np.float32)
        self.params['Wy'] = np.random.uniform(-std, std, (H, O)).astype(np.float32)
        for k in ['bf', 'bi', 'bc', 'bo']: self.params[k] = np.zeros((1, H), dtype=np.float32)
        self.params['by'] = np.zeros((1, O), dtype=np.float32)

        self.reset_grads()

    def reset_grads(self):
        self.grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.adam_m = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.adam_v = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.t = 0
        self.cache_data = None

    def prune(self, threshold_percentile=10):
        total, zeros = 0, 0
        for k in ['Wf', 'Wi', 'Wc', 'Wo', 'Wy']:
            w = self.params[k]
            mask = np.abs(w) > np.percentile(np.abs(w), threshold_percentile)
            w *= mask; self.adam_m[k] *= mask; self.adam_v[k] *= mask
            total += w.size; zeros += (w.size - np.sum(mask))
        return (zeros/total)*100

    def forward(self, inputs, h_prev=None, c_prev=None):
        if h_prev is None: h_prev = np.zeros((1, self.H), dtype=np.float32)
        if c_prev is None: c_prev = np.zeros((1, self.H), dtype=np.float32)
        
        outputs, h, c, cache_concat, cache_h, cache_c, cache_gates = _lstm_forward_jit(
            inputs, h_prev, c_prev,
            self.params['Wf'], self.params['Wi'], self.params['Wc'], self.params['Wo'], self.params['Wy'],
            self.params['bf'], self.params['bi'], self.params['bc'], self.params['bo'], self.params['by']
        )
        
        self.cache_data = (cache_concat, cache_h, cache_c, cache_gates, h_prev, c_prev)
        return outputs, h, c

    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY)
        cache_concat, cache_h, cache_c, cache_gates, h_init, c_init = self.cache_data
        
        dInputs, dWf, dWi, dWc, dWo, dWy, dbf, dbi, dbc, dbo, dby = _lstm_backward_jit(
            dY, cache_concat, cache_h, cache_c, cache_gates,
            self.params['Wf'], self.params['Wi'], self.params['Wc'], self.params['Wo'], self.params['Wy'],
            h_init, c_init
        )
        
        for k, g in zip(['Wf', 'Wi', 'Wc', 'Wo', 'Wy', 'bf', 'bi', 'bc', 'bo', 'by'],
                        [dWf, dWi, dWc, dWo, dWy, dbf, dbi, dbc, dbo, dby]):
            self.grads[k] += g
            
        return dInputs

    def apply_update(self, lr, batch_size):
        self.t += 1
        scale = 1.0 / batch_size
        
        total_norm = 0
        for k in self.grads: total_norm += np.sum(self.grads[k]**2)
        clip = 5.0 / (np.sqrt(total_norm) + 1e-6)
        if clip < 1: scale *= clip

        for k in self.params:
            _adam_update(self.params[k], self.grads[k] * scale, 
                         self.adam_m[k], self.adam_v[k], self.t, lr, 0.9, 0.999, 1e-7)
            self.grads[k].fill(0)

    def get_state(self):
        state = {}
        for k, v in self.params.items():
            q, s = quantize(v)
            state[f'q_{k}'] = q; state[f's_{k}'] = s
        return state

    def load_state(self, state):
        for k in self.params:
            self.params[k] = dequantize(state[f'q_{k}'], state[f's_{k}'])
        self.reset_grads()
'''

target_path = os.path.join("doxoade", "neural", "core.py")
with open(target_path, "w", encoding="utf-8") as f:
    f.write(CORE_CONTENT)

print(f"[RESCUE] Arquivo {target_path} restaurado com sucesso.")
print("Agora você pode rodar 'doxoade install numba' e retomar o desenvolvimento.")