# alfagold/core/transformer.py
import numpy as np
import pickle
import os
from .attention import execute_attention
from .tokenizer import AlfagoldTokenizer
# [FIX] Import centralizado
from .math_utils import softmax, gelu, d_gelu

class Alfagold:
    """
    Alfagold v2.1 (Modular Math).
    Suporta Aprendizado Multitarefa e usa matemática centralizada.
    """
    def __init__(self, vocab_size=2000, d_model=64, max_len=128, num_phases=6):
        self.d_model = d_model
        self.max_len = max_len
        self.vocab_size = vocab_size
        self.tokenizer = AlfagoldTokenizer()
        
        scale = 1.0 / np.sqrt(d_model)
        
        self.params = {
            'w_token': np.random.randn(vocab_size, d_model).astype(np.float32) * scale,
            'w_pos': self._create_positional_encoding(max_len, d_model),
            
            'Wq': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wk': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wv': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            'Wo': np.random.randn(d_model, d_model).astype(np.float32) * scale,
            
            'W1': np.random.randn(d_model, d_model * 4).astype(np.float32) * scale,
            'b1': np.zeros(d_model * 4, dtype=np.float32),
            'W2': np.random.randn(d_model * 4, d_model).astype(np.float32) * scale,
            'b2': np.zeros(d_model, dtype=np.float32),
            
            'W_phase': np.random.randn(d_model, num_phases).astype(np.float32) * scale,
            'b_phase': np.zeros(num_phases, dtype=np.float32)
        }

    def _create_positional_encoding(self, max_len, d_model):
        """Gera a matriz de senos e cossenos para posição."""
        pe = np.zeros((max_len, d_model), dtype=np.float32)
        position = np.arange(0, max_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)
        return pe

    def forward(self, token_ids, training=False):
        if len(token_ids) > self.max_len: token_ids = token_ids[:self.max_len]
        n = len(token_ids)
        cache = {}
        
        # 1. Embedding
        x = self.params['w_token'][token_ids] + self.params['w_pos'][:n]
        cache['token_ids'] = token_ids
        cache['x_emb'] = x

        # 2. Attention
        Q = np.dot(x, self.params['Wq'])
        K = np.dot(x, self.params['Wk'])
        V = np.dot(x, self.params['Wv'])
        cache['Q'], cache['K'], cache['V'] = Q, K, V
        
        attn_out, weights = execute_attention(Q, K, V, mask_type='causal')
        cache['attn_weights'] = weights
        
        x2 = x + np.dot(attn_out, self.params['Wo'])
        cache['x2'] = x2
        
        # 3. Feed Forward
        ff_hidden = np.dot(x2, self.params['W1']) + self.params['b1']
        ff_act = gelu(ff_hidden)
        cache['ff_hidden'] = ff_hidden
        cache['ff_act'] = ff_act
        
        ff_out = np.dot(ff_act, self.params['W2']) + self.params['b2']
        x_final = x2 + ff_out
        cache['x_final'] = x_final
        
        # 4. Heads
        logits_token = np.dot(x_final, self.params['w_token'].T)
        logits_phase = np.dot(x_final, self.params['W_phase']) + self.params['b_phase']
        
        return logits_token, logits_phase, cache

    def backward(self, d_logits_token, d_logits_phase, cache):
        grads = {k: np.zeros_like(v) for k, v in self.params.items()}
        
        # 1. Phase Head
        d_x_final_phase = np.dot(d_logits_phase, self.params['W_phase'].T)
        grads['W_phase'] = np.dot(cache['x_final'].T, d_logits_phase)
        grads['b_phase'] = np.sum(d_logits_phase, axis=0)

        # 2. Token Head
        d_x_final_token = np.dot(d_logits_token, self.params['w_token'])
        grads['w_token'] += np.dot(d_logits_token.T, cache['x_final'])

        # Soma
        d_x_final = d_x_final_token + d_x_final_phase
        
        # 3. FFN
        d_ff_out = d_x_final 
        grads['W2'] = np.dot(cache['ff_act'].T, d_ff_out)
        grads['b2'] = np.sum(d_ff_out, axis=0)
        
        d_ff_act = np.dot(d_ff_out, self.params['W2'].T)
        d_ff_hidden = d_ff_act * d_gelu(cache['ff_hidden'])
        
        grads['W1'] = np.dot(cache['x2'].T, d_ff_hidden)
        grads['b1'] = np.sum(d_ff_hidden, axis=0)
        
        d_x2 = np.dot(d_ff_hidden, self.params['W1'].T) + d_x_final
        
        # 4. Attention
        d_attn_out = np.dot(d_x2, self.params['Wo'].T)
        grads['Wo'] = np.dot(np.dot(cache['attn_weights'], cache['V']).T, d_x2)
        
        d_V = np.dot(cache['attn_weights'].T, d_attn_out)
        grads['Wv'] = np.dot(cache['x_emb'].T, d_V)
        
        d_weights = np.dot(d_attn_out, cache['V'].T)
        d_scores = d_weights * (1.0 / np.sqrt(self.d_model))
        
        d_Q = np.dot(d_scores, cache['K'])
        grads['Wq'] = np.dot(cache['x_emb'].T, d_Q)
        
        d_K = np.dot(d_scores.T, cache['Q'])
        grads['Wk'] = np.dot(cache['x_emb'].T, d_K)
        
        # 5. Embedding
        d_x_emb = (d_x2 + 
                   np.dot(d_Q, self.params['Wq'].T) + 
                   np.dot(d_K, self.params['Wk'].T) + 
                   np.dot(d_V, self.params['Wv'].T))
                   
        np.add.at(grads['w_token'], cache['token_ids'], d_x_emb)
        
        return grads

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {'params': self.params, 'tokenizer_state': self.tokenizer.__dict__}
        with open(path, 'wb') as f: pickle.dump(state, f)
            
    def load(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                state = pickle.load(f)
            if 'params' in state:
                for k, v in state['params'].items():
                    if k in self.params and self.params[k].shape == v.shape:
                        self.params[k] = v
                if 'tokenizer_state' in state:
                    self.tokenizer.__dict__.update(state['tokenizer_state'])