"""
DOXONET CORE v14.2 (Tensor Alignment).
Correção de desempacotamento de cache para backpropagation da DoxoAct.
"""
import numpy as np
import re
import json
import os

# --- UTILITÁRIOS MATEMÁTICOS ---
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60.0, 60.0)))

def dsigmoid(y):
    return y * (1.0 - y)

def dtanh(y):
    return 1.0 - y * y

def softmax(x):
    x_safe = np.nan_to_num(x)
    x_safe = np.clip(x_safe, -60, 60)
    e_x = np.exp(x_safe - np.max(x_safe, axis=1, keepdims=True))
    return e_x / (e_x.sum(axis=1, keepdims=True) + 1e-8)

# --- DOXO MATHEMATICS ---
def doxo_act(x):
    s = sigmoid(x)
    return (x * s) + (0.1 * np.sin(x))

def d_doxo_act(x, y=None):
    s = sigmoid(x)
    d_swish = s + (x * s * (1.0 - s))
    d_sin = 0.1 * np.cos(x)
    return d_swish + d_sin

# --- SERIALIZAÇÃO ---
def save_json(data, fp):
    with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=None)
def load_json(fp):
    with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
def quantize(w):
    w = np.nan_to_num(w); m = np.max(np.abs(w))
    if m == 0: return w.astype(np.int8).tolist(), 1.0
    s = m / 127.0; return np.round(w / s).astype(np.int8).tolist(), float(s)
def dequantize(q, s): return np.array(q, dtype=np.float32) * s

class Tokenizer:
    def __init__(self):
        self.vocabulario = {}; self.inverso = {}; self.contador = 0
        self.adicionar_token("<PAD>"); self.adicionar_token("<UNK>"); self.adicionar_token("ENDMARKER")
    def adicionar_token(self, token):
        if token not in self.vocabulario:
            self.vocabulario[token] = self.contador
            self.inverso[str(self.contador)] = token 
            self.contador += 1
    def treinar(self, textos):
        for texto in textos:
            for t in self._quebrar(texto): self.adicionar_token(t)
    def _quebrar(self, texto): return re.findall(r"[\w]+|[=+\-*/(){}:\[\]<>,.!]", texto)
    def converter_para_ids(self, texto):
        tokens = self._quebrar(texto)
        return np.array([self.vocabulario.get(t, 1) for t in tokens], dtype=np.int32)
    def to_dict(self): return {"vocabulario": self.vocabulario, "inverso": self.inverso, "contador": self.contador}
    @staticmethod
    def from_dict(d): t=Tokenizer(); t.vocabulario=d["vocabulario"]; t.inverso=d["inverso"]; t.contador=d["contador"]; return t

class CamadaEmbedding:
    def __init__(self, V, D):
        self.V, self.D = V, D
        self.E = np.random.randn(V, D).astype(np.float32) * 0.1
        self.grad_buffer = np.zeros_like(self.E); self.m = np.zeros_like(self.E); self.v = np.zeros_like(self.E); self.t = 0
        self.ultimo_input = None
        
    def init_symbolic(self, tokenizer):
        print("   🧬 Injetando DNA Simbólico...")
        keywords = ["def", "return", "if", "else", "elif", "pass", "ENDMARKER"]
        ops = ["+", "-", "*", "/", "%", "==", "!=", ">", "<", "="]
        pont = ["(", ")", ":", ","]
        for token, idx in tokenizer.vocabulario.items():
            if idx >= self.E.shape[0]: continue
            vec = self.E[idx]
            if token in keywords: vec[0] = 1.0
            elif token in ops: vec[1] = 1.0
            elif token in pont: vec[2] = 1.0
            elif token.isalnum(): vec[3] = 1.0
            self.E[idx] = vec

    def forward(self, ids):
        self.ultimo_input = ids
        return self.E[ids]
    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY)
        np.add.at(self.grad_buffer, self.ultimo_input, dY)
    def apply_update(self, lr, batch_size=1):
        self.t += 1
        self.m = 0.9 * self.m + 0.1 * self.grad_buffer
        self.v = 0.999 * self.v + 0.001 * (self.grad_buffer ** 2)
        m_hat = self.m / (1 - 0.9**self.t); v_hat = self.v / (1 - 0.999**self.t)
        self.E -= lr * m_hat / (np.sqrt(v_hat) + 1e-7)
        self.grad_buffer.fill(0)
    
    def get_state_dict(self): return {'E': [quantize(self.E)[0], quantize(self.E)[1]]}
    
    def load_state_dict(self, s):
        # Carregamento Elástico
        if 'E' in s: loaded_E = dequantize(s['E'][0], s['E'][1])
        elif 'q_E' in s: loaded_E = dequantize(s['q_E'], s['s_E'])
        else: return

        if self.E.shape[0] >= loaded_E.shape[0]:
            rows = loaded_E.shape[0]
            self.E[:rows] = loaded_E
            print(f"   🌱 Embedding Expandido/Preservado ({rows} -> {self.E.shape[0]} tokens)")
        else:
            self.E = loaded_E[:self.E.shape[0]]

        self.m = np.zeros_like(self.E); self.v = np.zeros_like(self.E); self.t = 0

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

    def prune(self, threshold_percentile=10):
        total, zeros = 0, 0
        for k in ['Wf', 'Wi', 'Wc', 'Wo', 'Wy']:
            w = self.params[k]
            mask = np.abs(w) > np.percentile(np.abs(w), threshold_percentile)
            w *= mask.astype(np.float32)
            self.adam_m[k] *= mask.astype(np.float32); self.adam_v[k] *= mask.astype(np.float32)
            total += w.size; zeros += (w.size - np.sum(mask))
        return (zeros/total)*100

    def forward(self, inputs, h_prev=None, c_prev=None):
        if h_prev is None: h_prev = np.zeros((1, self.H), dtype=np.float32)
        if c_prev is None: c_prev = np.zeros((1, self.H), dtype=np.float32)
        self.cache = []; outputs = []; h, c = h_prev, c_prev
        Wf, Wi, Wc, Wo, Wy = [self.params[k] for k in ['Wf', 'Wi', 'Wc', 'Wo', 'Wy']]
        bf, bi, bc, bo, by = [self.params[k] for k in ['bf', 'bi', 'bc', 'bo', 'by']]
        
        for t in range(len(inputs)):
            x = inputs[t].reshape(1, -1); concat = np.concatenate((x, h), axis=1)
            f = sigmoid(np.dot(concat, Wf) + bf); i = sigmoid(np.dot(concat, Wi) + bi)
            c_bar = np.tanh(np.dot(concat, Wc) + bc); o = sigmoid(np.dot(concat, Wo) + bo)
            c = f * c + i * c_bar; tanh_c = doxo_act(c); h = o * tanh_c
            y = np.dot(h, Wy) + by
            # Cache sem c_prev redundante, mas precisamos dele para backprop
            self.cache.append((concat, f, i, c_bar, c, tanh_c, o, h))
            outputs.append(y)
        return np.array(outputs), h, c

    def accumulate_grad(self, dY):
        dY = np.nan_to_num(dY); inputs_len = len(self.cache)
        dInputs = np.zeros((inputs_len, self.I), dtype=np.float32)
        dh_next = np.zeros((1, self.H), dtype=np.float32); dc_next = np.zeros((1, self.H), dtype=np.float32)
        Wf, Wi, Wc, Wo, Wy = [self.params[k] for k in ['Wf', 'Wi', 'Wc', 'Wo', 'Wy']]
        
        for t in reversed(range(inputs_len)):
            dy = dY[t].reshape(1, -1)
            # CORREÇÃO: Unpack completo
            concat, f, i, c_bar, c_curr, h_act_curr, o, h_curr = self.cache[t]
            
            # Recupera c_prev do passo anterior (ou do init se t=0)
            if t > 0:
                # O índice 4 da tupla é 'c'
                c_prev = self.cache[t-1][4]
            else:
                # Se não tem anterior, assume zero ou estado inicial
                c_prev = np.zeros_like(c_curr)

            self.grads['Wy'] += np.dot(h_curr.T, dy); self.grads['by'] += dy
            dh = np.dot(dy, Wy.T) + dh_next
            do = dh * h_act_curr; do_raw = dsigmoid(o) * do
            
            # Gradiente da DoxoAct
            dc = dc_next + (dh * o * d_doxo_act(c_curr))
            
            dc_bar = dc * i; dc_bar_raw = dtanh(c_bar) * dc_bar
            di = dc * c_bar; di_raw = dsigmoid(i) * di
            df = dc * c_prev; df_raw = dsigmoid(f) * df
            dc_next = dc * f
            
            self.grads['Wo'] += np.dot(concat.T, do_raw); self.grads['bo'] += do_raw
            self.grads['Wc'] += np.dot(concat.T, dc_bar_raw); self.grads['bc'] += dc_bar_raw
            self.grads['Wi'] += np.dot(concat.T, di_raw); self.grads['bi'] += di_raw
            self.grads['Wf'] += np.dot(concat.T, df_raw); self.grads['bf'] += df_raw
            
            d_concat = (np.dot(do_raw, self.params['Wo'].T) + np.dot(dc_bar_raw, self.params['Wc'].T) + 
                        np.dot(di_raw, self.params['Wi'].T) + np.dot(df_raw, self.params['Wf'].T))
            dInputs[t] = d_concat[0, :self.I]; dh_next = d_concat[0, self.I:]
        return dInputs

    def apply_update(self, lr, batch_size):
        self.t += 1; scale = 1.0 / batch_size
        tn = sum(np.sum(g**2) for g in self.grads.values()); clip = 5.0 / (np.sqrt(tn) + 1e-6)
        if clip < 1: scale *= clip
        for k in self.params:
            g = self.grads[k] * scale
            self.adam_m[k] = 0.9 * self.adam_m[k] + 0.1 * g
            self.adam_v[k] = 0.999 * self.adam_v[k] + 0.001 * (g**2)
            m_hat = self.adam_m[k] / (1 - 0.9**self.t)
            v_hat = self.adam_v[k] / (1 - 0.999**self.t)
            self.params[k] -= lr * m_hat / (np.sqrt(v_hat) + 1e-7)
            self.grads[k].fill(0)

    def get_state_dict(self):
        return {k: quantize(v) for k, v in self.params.items()}

    def load_state_dict(self, state):
        for k in self.params:
            if k in state:
                val = state[k]
                loaded_param = dequantize(val[0], val[1])
                # Carregamento Elástico
                if k in ['Wy', 'by']:
                    current_shape = self.params[k].shape
                    loaded_shape = loaded_param.shape
                    if current_shape != loaded_shape:
                        cols = min(current_shape[1], loaded_shape[1])
                        if len(current_shape) > 1: self.params[k][:, :cols] = loaded_param[:, :cols]
                        else: self.params[k][:cols] = loaded_param[:cols]
                        print(f"   🌱 {k} Adaptado: {loaded_shape[1]} -> {current_shape[1]}")
                        continue
                self.params[k] = loaded_param
            elif f'q_{k}' in state:
                self.params[k] = dequantize(state[f'q_{k}'], state[f's_{k}'])
        self.reset_grads()