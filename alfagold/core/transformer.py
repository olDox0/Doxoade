# alfagold/core/transformer.py
import numpy as np
import os
import pickle
from typing import Dict, Tuple

from .tokenizer import AlfagoldTokenizer
from .persistence import save_model_state, load_model_state
from .math_lut import LUT 

class Alfagold:
    """
    Alfagold v5.0 (Math Fix).
    Correção crítica de gradientes: Softmax Jacobian, LayerNorm e Split Embeddings.
    """
    def __init__(self, vocab_size: int = 2000, d_model: int = 64, max_len: int = 128, num_phases: int = 6):
        self.d_model = d_model
        self.max_len = max_len
        self.vocab_size = vocab_size
        self.num_phases = num_phases
        self.tokenizer = AlfagoldTokenizer()
        
        scale = 1.0 / np.sqrt(d_model)
        
        self.params = {
            # 1. Embeddings (Separados para evitar conflito de gradiente)
            'w_token': np.random.randn(vocab_size, d_model).astype(np.float32) * scale,
            'w_pos': self._create_positional_encoding(max_len, d_model),
            
            # 2. LayerNorm 1 (Antes da Attention)
            'ln1_gamma': np.ones(d_model, dtype=np.float32),
            'ln1_beta': np.zeros(d_model, dtype=np.float32),

            # 3. Attention
            'Wq': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wk': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wv': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wo': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            
            # 4. LayerNorm 2 (Antes da FFN)
            'ln2_gamma': np.ones(d_model, dtype=np.float32),
            'ln2_beta': np.zeros(d_model, dtype=np.float32),

            # 5. Feed Forward
            'W1': np.random.randn(d_model, d_model * 4).astype(np.float32) * scale,
            'b1': np.zeros(d_model * 4, dtype=np.float32),
            'W2': np.random.randn(d_model * 4, d_model).astype(np.float32) * scale,
            'b2': np.zeros(d_model, dtype=np.float32),
            
            # 6. Heads (Output Projection separada)
            'w_out': np.random.randn(d_model, vocab_size).astype(np.float32) * scale,
            'W_phase': np.random.randn(d_model, num_phases).astype(np.float32) * scale,
            'b_phase': np.zeros(num_phases, dtype=np.float32)
        }
        
        # Máscara Causal Pré-computada
        self.causal_mask = np.triu(np.ones((max_len, max_len)), k=1) * -1e9

    def _create_positional_encoding(self, max_len: int, d_model: int) -> np.ndarray:
        pe = np.zeros((max_len, d_model), dtype=np.float32)
        position = np.arange(0, max_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)
        return pe

    def _layer_norm_forward(self, x, gamma, beta):
        """Retorna (normalizado, (mean, var, x_hat)) para cache."""
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        x_hat = (x - mean) / np.sqrt(var + 1e-5)
        out = gamma * x_hat + beta
        return out, (mean, var, x_hat)

    def _layer_norm_backward(self, dout, cache, gamma):
        """Gradiente correto da LayerNorm."""
        mean, var, x_hat = cache
        N, D = dout.shape
        
        dgamma = np.sum(dout * x_hat, axis=0)
        dbeta = np.sum(dout, axis=0)
        
        dx_hat = dout * gamma
        ivar = 1.0 / np.sqrt(var + 1e-5)
        
        # Fórmula analítica do gradiente da LN
        dx = (1.0 / D) * ivar * (D * dx_hat - np.sum(dx_hat, axis=1, keepdims=True) - x_hat * np.sum(dx_hat * x_hat, axis=1, keepdims=True))
        
        return dx, dgamma, dbeta

    def forward(self, token_ids: list, training: bool = False) -> Tuple[np.ndarray, np.ndarray, Dict]:
        n = len(token_ids)
        if n > self.max_len: 
            token_ids = token_ids[:self.max_len]
            n = self.max_len
            
        cache = {}
        cache['token_ids'] = token_ids
        
        # 1. Embedding + Pos
        x = self.params['w_token'][token_ids] + self.params['w_pos'][:n]
        
        # --- BLOCO 1: ATENÇÃO (Pre-Norm) ---
        x_ln1, cache['ln1'] = self._layer_norm_forward(x, self.params['ln1_gamma'], self.params['ln1_beta'])
        
        # Projeções
        Q = np.dot(x_ln1, self.params['Wq'])
        K = np.dot(x_ln1, self.params['Wk'])
        V = np.dot(x_ln1, self.params['Wv'])
        cache['K'], cache['V'] = K, V # Q não é necessário guardar se tivermos scores, mas guardamos para segurança
        cache['Q'] = Q
        
        # Scaled Dot-Product Attention
        scores = np.matmul(Q, K.T) / np.sqrt(self.d_model)
        
        # Máscara Causal
        mask = self.causal_mask[:n, :n]
        scores += mask
        
        # Softmax com LUT
        # e_x = LUT.exp(scores - np.max(scores, axis=-1, keepdims=True)) 
        # Usamos numpy puro no softmax por segurança numérica crítica aqui
        e_x = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
        attn_weights = e_x / np.sum(e_x, axis=-1, keepdims=True)
        cache['attn_weights'] = attn_weights
        
        attn_out = np.matmul(attn_weights, V)
        
        # Projeção Output e Residual
        x_attn = np.dot(attn_out, self.params['Wo'])
        x2 = x + x_attn # Residual 1
        
        # --- BLOCO 2: FFN (Pre-Norm) ---
        x_ln2, cache['ln2'] = self._layer_norm_forward(x2, self.params['ln2_gamma'], self.params['ln2_beta'])
        
        ff_hidden = np.dot(x_ln2, self.params['W1']) + self.params['b1']
        ff_act = LUT.gelu(ff_hidden)
        cache['ff_hidden'] = ff_hidden
        cache['ff_act'] = ff_act
        
        ff_out = np.dot(ff_act, self.params['W2']) + self.params['b2']
        x_final = x2 + ff_out # Residual 2
        cache['x_final'] = x_final # Necessário para backprop do Phase Head
        
        # 4. Heads (Agora usando w_out separado)
        logits_token = np.dot(x_final, self.params['w_out']) 
        logits_phase = np.dot(x_final, self.params['W_phase']) + self.params['b_phase']
        
        return logits_token, logits_phase, cache

    def backward(self, d_logits_token, d_logits_phase, cache):
        grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        n = d_logits_token.shape[0]
        
        # 1. Backprop Heads
        # Phase
        d_x_final = np.dot(d_logits_phase, self.params['W_phase'].T)
        grads['W_phase'] = np.dot(cache['x_final'].T, d_logits_phase)
        grads['b_phase'] = np.sum(d_logits_phase, axis=0)

        # Token (Usando w_out, não w_token)
        d_x_final += np.dot(d_logits_token, self.params['w_out'].T)
        grads['w_out'] = np.dot(cache['x_final'].T, d_logits_token)
        
        # 2. Backprop FFN (Residual: d_x2 passa direto)
        d_x2 = d_x_final # Começa com o residual
        
        # Caminho FFN
        # Passa pela LN2 no sentido inverso? Não, a arquitetura é Pre-Norm.
        # x_final = x2 + FFN(LN2(x2))
        # dL/dx2 = dL/dx_final + dL/dFFN * dFFN/dLN2 * dLN2/dx2
        
        d_ff_out = d_x_final # O gradiente que entra na FFN
        grads['W2'] = np.dot(cache['ff_act'].T, d_ff_out)
        grads['b2'] = np.sum(d_ff_out, axis=0)
        
        d_ff_act = np.dot(d_ff_out, self.params['W2'].T)
        d_ff_hidden = d_ff_act * LUT.d_gelu(cache['ff_hidden'])
        
        grads['W1'] = np.dot(cache['ln2'][0].T, d_ff_hidden) # ln2[0] é o input normalizado
        grads['b1'] = np.sum(d_ff_hidden, axis=0)
        
        d_x_ln2 = np.dot(d_ff_hidden, self.params['W1'].T)
        d_x2_norm, grads['ln2_gamma'], grads['ln2_beta'] = self._layer_norm_backward(
            d_x_ln2, cache['ln2'], self.params['ln2_gamma']
        )
        
        d_x2 += d_x2_norm # Soma o ramo da FFN ao residual
        
        # 3. Backprop Attention (Residual: d_x passa direto)
        d_x = d_x2 # Começa com residual
        
        # Caminho Attention
        # x2 = x + Attn(LN1(x))
        d_attn_out = d_x2
        grads['Wo'] = np.dot(np.dot(cache['attn_weights'], cache['V']).T, d_attn_out)
        
        d_V_weighted = np.dot(d_attn_out, self.params['Wo'].T)
        
        # --- CORREÇÃO DO SOFTMAX BACKWARD (JACOBIANO) ---
        # d_attn_weights = d_V_weighted * V.T
        d_attn_weights = np.dot(d_V_weighted, cache['V'].T)
        
        # Softmax Gradient: S * (G - sum(S*G))
        # S = cache['attn_weights'], G = d_attn_weights
        sum_sg = np.sum(cache['attn_weights'] * d_attn_weights, axis=-1, keepdims=True)
        d_scores = cache['attn_weights'] * (d_attn_weights - sum_sg)
        
        # Scale
        d_scores *= (1.0 / np.sqrt(self.d_model))
        
        # Causal Mask Gradient (Zero onde mask era -inf)
        # Como -inf vira 0 no softmax, o gradiente já é zerado naturalmente pela multiplicação por S
        # mas podemos garantir explicitamente
        # d_scores *= (self.causal_mask[:n, :n] == 0) 
        
        d_Q = np.dot(d_scores, cache['K'])
        d_K = np.dot(d_scores.T, cache['Q'])
        d_V = np.dot(cache['attn_weights'].T, d_V_weighted)
        
        # Backprop através das projeções lineares
        # Todas recebem input de LN1(x)
        x_ln1_input = cache['ln1'][0]
        
        grads['Wq'] = np.dot(x_ln1_input.T, d_Q)
        grads['Wk'] = np.dot(x_ln1_input.T, d_K)
        grads['Wv'] = np.dot(x_ln1_input.T, d_V)
        
        d_x_ln1 = (np.dot(d_Q, self.params['Wq'].T) + 
                   np.dot(d_K, self.params['Wk'].T) + 
                   np.dot(d_V, self.params['Wv'].T))
                   
        d_x_norm, grads['ln1_gamma'], grads['ln1_beta'] = self._layer_norm_backward(
            d_x_ln1, cache['ln1'], self.params['ln1_gamma']
        )
        
        d_x += d_x_norm
        
        # 4. Embedding Gradient
        np.add.at(grads['w_token'], cache['token_ids'], d_x)
        
        return grads
        
    def save(self, path: str):
        base_path = path.replace('.pkl', '')
        config = {
            'vocab_size': self.vocab_size,
            'd_model': self.d_model,
            'max_len': self.max_len,
            'num_phases': self.num_phases,
            'tokenizer_state': self.tokenizer.get_state()
        }
        save_model_state(base_path, self.params, config)

    def load(self, path: str):
        base_path = path.replace('.pkl', '')
        try:
            params, config = load_model_state(base_path)
            for k, v in params.items():
                if k in self.params:
                    # Permite carregar w_token antigo em w_out se necessário, mas ideal é treinar do zero
                    if self.params[k].shape == v.shape:
                        self.params[k] = v
            if 'tokenizer_state' in config:
                self.tokenizer.set_state(config['tokenizer_state'])
        except Exception: pass