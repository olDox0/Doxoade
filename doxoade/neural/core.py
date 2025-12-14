# doxoade/neural/core.py
"""
DOXONET CORE - Engine Neural (LSTM + BPTT).
Implementação NumPy pura de redes neurais para processamento de linguagem.
Parte integrante da arquitetura Gênese Neuro-Simbólica.
"""
import numpy as np
import re
import pickle
import os

# --- FUNÇÕES DE ATIVAÇÃO ---
def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

def dsigmoid(y):
    return y * (1 - y)

def dtanh(y):
    return 1 - y * y

def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=1, keepdims=True)

# --- TOKENIZER ---
class Tokenizer:
    def __init__(self):
        self.vocabulario = {} 
        self.inverso = {}     
        self.contador = 0
        self.adicionar_token("<PAD>")
        self.adicionar_token("<UNK>")
        self.adicionar_token("ENDMARKER")
        # self.adicionar_token("<EOS>")
    
    def adicionar_token(self, token):
        if token not in self.vocabulario:
            self.vocabulario[token] = self.contador
            self.inverso[self.contador] = token
            self.contador += 1
            
    def treinar(self, textos):
        for texto in textos:
            for t in self._quebrar(texto):
                self.adicionar_token(t)

    def _quebrar(self, texto):
        # Regex ajustada para capturar sintaxe Python
        padrao = r"[\w]+|[=+\-*/(){}:\[\]<>,.!]"
        return re.findall(padrao, texto)

    def converter_para_ids(self, texto):
        tokens = self._quebrar(texto)
        return np.array([self.vocabulario.get(t, 1) for t in tokens])
    
    def converter_para_texto(self, ids):
        tokens = []
        for i in ids:
            t = self.inverso.get(i, "?")
            if t not in ["<PAD>", "<UNK>"]: tokens.append(t)
        return " ".join(tokens)

# --- EMBEDDINGS ---
class CamadaEmbedding:
    def __init__(self, tamanho_vocabulario, dimensao_embedding):
        self.V = tamanho_vocabulario
        self.D = dimensao_embedding
        self.E = np.random.randn(self.V, self.D) * 0.1
        self.ultimo_input = None

    def forward(self, ids):
        self.ultimo_input = ids
        return self.E[ids]

    def backward(self, dY, lr):
        np.add.at(self.E, self.ultimo_input, -lr * dY)

# --- LSTM ---
class LSTM:
    def __init__(self, input_size, hidden_size, output_size):
        self.H = hidden_size
        self.I = input_size
        self.O = output_size
        
        # Inicialização Xavier
        std = 1.0 / np.sqrt(hidden_size)
        self.Wf = np.random.uniform(-std, std, (self.I + self.H, self.H))
        self.Wi = np.random.uniform(-std, std, (self.I + self.H, self.H))
        self.Wc = np.random.uniform(-std, std, (self.I + self.H, self.H))
        self.Wo = np.random.uniform(-std, std, (self.I + self.H, self.H))
        self.Wy = np.random.uniform(-std, std, (self.H, self.O))
        
        self.bf = np.zeros((1, self.H))
        self.bi = np.zeros((1, self.H))
        self.bc = np.zeros((1, self.H))
        self.bo = np.zeros((1, self.H))
        self.by = np.zeros((1, self.O))

    def forward(self, inputs, h_prev=None, c_prev=None):
        if h_prev is None: h_prev = np.zeros((1, self.H))
        if c_prev is None: c_prev = np.zeros((1, self.H))
            
        self.cache = []
        outputs = []
        h, c = h_prev, c_prev
        
        for t in range(len(inputs)):
            x = inputs[t].reshape(1, -1)
            concat = np.hstack((x, h))
            
            f = sigmoid(np.dot(concat, self.Wf) + self.bf)
            i = sigmoid(np.dot(concat, self.Wi) + self.bi)
            c_bar = np.tanh(np.dot(concat, self.Wc) + self.bc)
            c = f * c + i * c_bar
            o = sigmoid(np.dot(concat, self.Wo) + self.bo)
            h = o * np.tanh(c)
            y = np.dot(h, self.Wy) + self.by
            
            self.cache.append((x, concat, f, i, c_bar, c, o, h, c_prev))
            outputs.append(y)
            c_prev = c
            
        return np.array(outputs), h, c

    def clip_gradients(self, gradients, max_norm=5.0):
        """
        (Técnica Nox) Impede explosão de gradientes normalizando o vetor global.
        """
        total_norm = 0
        for g in gradients:
            total_norm += np.sum(g ** 2)
        total_norm = np.sqrt(total_norm)
        
        clip_coef = max_norm / (total_norm + 1e-6)
        if clip_coef < 1:
            for g in gradients:
                g *= clip_coef
        return gradients

    def backward(self, dY, lr=0.1):
        inputs_len = len(self.cache)
        dInputs = np.zeros((inputs_len, self.I))
        
        dWf, dWi, dWc, dWo, dWy = [np.zeros_like(w) for w in (self.Wf, self.Wi, self.Wc, self.Wo, self.Wy)]
        dbf, dbi, dbc, dbo, dby = [np.zeros_like(b) for b in (self.bf, self.bi, self.bc, self.bo, self.by)]
        
        dh_next = np.zeros((1, self.H))
        dc_next = np.zeros((1, self.H))
        
        for t in reversed(range(inputs_len)):
            dy = dY[t].reshape(1, -1)
            x, concat, f, i, c_bar, c, o, h, c_prev = self.cache[t]
            
            dWy += np.dot(h.T, dy)
            dby += dy
            dh = np.dot(dy, self.Wy.T) + dh_next
            
            do = dh * np.tanh(c)
            do_raw = dsigmoid(o) * do
            dc = dc_next + (dh * o * dtanh(np.tanh(c)))
            dc_bar = dc * i
            dc_bar_raw = dtanh(c_bar) * dc_bar
            di = dc * c_bar
            di_raw = dsigmoid(i) * di
            df = dc * c_prev
            df_raw = dsigmoid(f) * df
            dc_next = dc * f
            
            # Acumulação
            dWo += np.dot(concat.T, do_raw); dbo += do_raw
            dWc += np.dot(concat.T, dc_bar_raw); dbc += dc_bar_raw
            dWi += np.dot(concat.T, di_raw); dbi += di_raw
            dWf += np.dot(concat.T, df_raw); dbf += df_raw
            
            d_concat = (np.dot(do_raw, self.Wo.T) + np.dot(dc_bar_raw, self.Wc.T) + 
                        np.dot(di_raw, self.Wi.T) + np.dot(df_raw, self.Wf.T))
            
            dInputs[t] = d_concat[0, :self.I]
            dh_next = d_concat[0, self.I:]
            
        # Clipping para evitar explosão de gradientes
        for d in [dWf, dWi, dWc, dWo, dWy, dbf, dbi, dbc, dbo, dby, dInputs]:
            np.clip(d, -5, 5, out=d)
            
        # ANTES DE ATUALIZAR OS PESOS:
        # Agrupar todos os gradientes numa lista
        all_grads = [dWf, dWi, dWc, dWo, dWy, dbf, dbi, dbc, dbo, dby]
        
        # Aplicar Clipping Global (Estabilidade)
        self.clip_gradients(all_grads, max_norm=1.0)
        
        # Atualizar (SGD com Momentum Simulado - Opcional, aqui SGD puro por simplicidade)
        self.Wf -= lr * dWf
        self.Wi -= lr * dWi
        self.Wc -= lr * dWc
        self.Wo -= lr * dWo
        self.Wy -= lr * dWy
        self.bf -= lr * dbf
        self.bi -= lr * dbi
        self.bc -= lr * dbc
        self.bo -= lr * dbo
        self.by -= lr * dby
        
        return dInputs
