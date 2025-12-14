# doxoade/neural/core.py
"""
DOXONET CORE v9.0 (Icarus Patch).
Correção crítica de fluxo de memória LSTM e otimização de buffers.
Status: Stable / CPU-Optimized.
"""
import numpy as np
import re
import pickle
import os

# --- UTILITÁRIOS BLINDADOS ---
def sigmoid(x):
    # Clip para evitar overflow, float32 friendly
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))

def dsigmoid(y):
    return y * (1.0 - y)

def dtanh(y):
    return 1.0 - y * y

def softmax(x):
    # Softmax numericamente estável
    x_safe = np.nan_to_num(x)
    x_safe = np.clip(x_safe, -60, 60)
    e_x = np.exp(x_safe - np.max(x_safe, axis=1, keepdims=True))
    return e_x / (e_x.sum(axis=1, keepdims=True) + 1e-8)

# --- QUANTIZAÇÃO ---
def quantize(weights):
    weights = np.nan_to_num(weights)
    max_val = np.max(np.abs(weights))
    if max_val == 0: return weights.astype(np.int8), 1.0
    scale = max_val / 127.0
    q_weights = np.round(weights / scale).astype(np.int8)
    return q_weights, scale

def dequantize(q_weights, scale):
    return q_weights.astype(np.float32) * scale

# --- TOKENIZER ---
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

# --- EMBEDDING ---
class CamadaEmbedding:
    def __init__(self, V, D):
        self.V, self.D = V, D
        self.E = np.random.randn(V, D).astype(np.float32) * 0.1
        self.grad_buffer = np.zeros_like(self.E)
        
        # Adam State
        self.m = np.zeros_like(self.E)
        self.v = np.zeros_like(self.E)
        self.t = 0
        self.ultimo_input = None

    def forward(self, ids):
        self.ultimo_input = ids
        return self.E[ids]

    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY)
        np.add.at(self.grad_buffer, self.ultimo_input, dY)

    def apply_update(self, lr, batch_size=1, beta1=0.9, beta2=0.999, epsilon=1e-7):
        self.t += 1
        self.m = beta1 * self.m + (1 - beta1) * self.grad_buffer
        self.v = beta2 * self.v + (1 - beta2) * (self.grad_buffer ** 2)
        m_hat = self.m / (1 - beta1 ** self.t)
        v_hat = self.v / (1 - beta2 ** self.t)
        
        update = lr * m_hat / (np.sqrt(v_hat) + epsilon)
        self.E -= np.nan_to_num(update)
        self.grad_buffer.fill(0)

    def get_state(self):
        q_E, s_E = quantize(self.E)
        return {'q_E': q_E, 's_E': s_E, 'm': self.m, 'v': self.v, 't': self.t}

    def load_state(self, s): 
        self.E = dequantize(s['q_E'], s['s_E'])
        if 'm' in s:
            self.m = s['m']; self.v = s['v']; self.t = s['t']
        else:
            self.m.fill(0); self.v.fill(0); self.t = 0

# --- LSTM (FUSED + CORRECTED) ---
class LSTM:
    def __init__(self, I, H, O):
        self.I, self.H, self.O = I, H, O
        std = np.float32(1.0 / np.sqrt(H))
        
        self.params = {}
        for k in ['Wf', 'Wi', 'Wc', 'Wo']: 
            self.params[k] = np.random.uniform(-std, std, (I + H, H)).astype(np.float32)
        self.params['Wy'] = np.random.uniform(-std, std, (H, O)).astype(np.float32)
        
        for k in ['bf', 'bi', 'bc', 'bo']: 
            self.params[k] = np.zeros((1, H), dtype=np.float32)
        self.params['by'] = np.zeros((1, O), dtype=np.float32)

        self._init_grads_and_opt()

    def _init_grads_and_opt(self):
        self.grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.adam_m = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.adam_v = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.t = 0

    def prune(self, threshold_percentile=10):
        total, zeros = 0, 0
        target_keys = ['Wf', 'Wi', 'Wc', 'Wo', 'Wy']
        for k in target_keys:
            w = self.params[k]
            threshold = np.percentile(np.abs(w), threshold_percentile)
            mask = np.abs(w) > threshold
            self.params[k] *= mask.astype(np.float32)
            self.adam_m[k] *= mask.astype(np.float32)
            self.adam_v[k] *= mask.astype(np.float32)
            total += w.size; zeros += (w.size - np.sum(mask))
        return (zeros / total) * 100

    def forward(self, inputs, h_prev=None, c_prev=None):
        if h_prev is None: h_prev = np.zeros((1, self.H), dtype=np.float32)
        if c_prev is None: c_prev = np.zeros((1, self.H), dtype=np.float32)
        
        self.cache = []
        outputs = []
        h, c = h_prev, c_prev
        
        # Unpack para acesso rápido
        Wf, Wi, Wc, Wo, Wy = self.params['Wf'], self.params['Wi'], self.params['Wc'], self.params['Wo'], self.params['Wy']
        bf, bi, bc, bo, by = self.params['bf'], self.params['bi'], self.params['bc'], self.params['bo'], self.params['by']
        
        for t in range(len(inputs)):
            x = inputs[t].reshape(1, -1)
            
            # OTIMIZAÇÃO: concatenate é ligeiramente mais rápido que hstack para tuplas
            concat = np.concatenate((x, h), axis=1)
            
            f = sigmoid(np.dot(concat, Wf) + bf)
            i = sigmoid(np.dot(concat, Wi) + bi)
            c_bar = np.tanh(np.dot(concat, Wc) + bc)
            o = sigmoid(np.dot(concat, Wo) + bo)
            
            # Estado da Célula
            c_next = f * c + i * c_bar
            tanh_c = np.tanh(c_next)
            h_next = o * tanh_c
            
            # Output
            y = np.dot(h_next, Wy) + by
            
            # Cache Otimizado (Icarus recommendation):
            # Guardamos c_prev real para o backward do forget gate
            self.cache.append((concat, f, i, c_bar, c, tanh_c, o, h_next))
            
            outputs.append(y)
            
            # BUGFIX CRÍTICO: Atualizar os estados para o próximo loop!
            h = h_next
            c = c_next
            
        return np.array(outputs), h, c

    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY)
        inputs_len = len(self.cache)
        dInputs = np.zeros((inputs_len, self.I), dtype=np.float32)
        
        dh_next = np.zeros((1, self.H), dtype=np.float32)
        dc_next = np.zeros((1, self.H), dtype=np.float32)
        
        Wf, Wi, Wc, Wo, Wy = self.params['Wf'], self.params['Wi'], self.params['Wc'], self.params['Wo'], self.params['Wy']
        
        for t in reversed(range(inputs_len)):
            dy = dY[t].reshape(1, -1)
            
            # Recupera cache
            concat, f, i, c_bar, c_prev, tanh_c_curr, o, h_curr = self.cache[t]
            
            # 1. Output Grads
            self.grads['Wy'] += np.dot(h_curr.T, dy)
            self.grads['by'] += dy
            
            # 2. Hidden Grads
            dh = np.dot(dy, Wy.T) + dh_next
            
            # 3. Gates Grads
            do = dh * tanh_c_curr
            do_raw = dsigmoid(o) * do
            
            # dc = dc_next + dh * o * (1 - tanh^2(c)) -> usando tanh_c cacheado
            dc = dc_next + (dh * o * dtanh(tanh_c_curr))
            
            dc_bar = dc * i
            dc_bar_raw = dtanh(c_bar) * dc_bar
            
            di = dc * c_bar
            di_raw = dsigmoid(i) * di
            
            df = dc * c_prev
            df_raw = dsigmoid(f) * df
            
            # Gradiente para c anterior
            dc_next = dc * f
            
            # 4. Weights Accumulation
            self.grads['Wo'] += np.dot(concat.T, do_raw); self.grads['bo'] += do_raw
            self.grads['Wc'] += np.dot(concat.T, dc_bar_raw); self.grads['bc'] += dc_bar_raw
            self.grads['Wi'] += np.dot(concat.T, di_raw); self.grads['bi'] += di_raw
            self.grads['Wf'] += np.dot(concat.T, df_raw); self.grads['bf'] += df_raw
            
            # 5. Input Grads
            d_concat = (np.dot(do_raw, Wo.T) + np.dot(dc_bar_raw, Wc.T) + 
                        np.dot(di_raw, Wi.T) + np.dot(df_raw, Wf.T))
            
            dInputs[t] = d_concat[0, :self.I]
            dh_next = d_concat[0, self.I:]
            
        return dInputs

    def apply_update(self, lr, batch_size, beta1=0.9, beta2=0.999, epsilon=1e-7):
        self.t += 1
        scale = (1.0 / batch_size)
        
        total_norm = 0
        for k in self.grads: total_norm += np.sum(self.grads[k]**2)
        clip = 5.0 / (np.sqrt(total_norm) + 1e-6)
        if clip < 1: scale *= clip

        for k in self.params:
            g = self.grads[k] * scale
            self.adam_m[k] = beta1 * self.adam_m[k] + (1 - beta1) * g
            self.adam_v[k] = beta2 * self.adam_v[k] + (1 - beta2) * (g ** 2)
            
            m_hat = self.adam_m[k] / (1 - beta1 ** self.t)
            v_hat = self.adam_v[k] / (1 - beta2 ** self.t)
            
            update = lr * m_hat / (np.sqrt(v_hat) + epsilon)
            self.params[k] -= np.nan_to_num(update)
            self.grads[k].fill(0)

    def get_state(self):
        state = {}
        for k, v in self.params.items():
            q, s = quantize(v)
            state[f'q_{k}'] = q; state[f's_{k}'] = s
        state['adam_m'] = self.adam_m
        state['adam_v'] = self.adam_v
        state['t'] = self.t
        return state

    def load_state(self, state):
        for k in self.params:
            self.params[k] = dequantize(state[f'q_{k}'], state[f's_{k}'])
        
        if 'adam_m' in state:
            self.adam_m = state['adam_m']
            self.adam_v = state['adam_v']
            self.t = state['t']
        else:
            self._init_grads_and_opt()
            
        self.grads = {k: np.zeros_like(v) for k, v in self.params.items()}