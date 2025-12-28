# doxoade/neural/hrl.py
import numpy as np
import os
import pickle
from .core import softmax

class HRLManager:
    def __init__(self, input_dim=64, num_options=3):
        self.input_dim = input_dim
        self.num_options = num_options
        self.W1 = np.random.randn(input_dim, 32) * 0.1
        self.W2 = np.random.randn(32, num_options) * 0.1
        self.current_option = 0

    def select_option(self, state_vector):
        h = np.maximum(0, np.dot(state_vector, self.W1))
        logits = np.dot(h, self.W2)
        probs = softmax(logits.reshape(1, -1)).flatten()
        option = np.argmax(probs)
        self.current_option = option
        return option

class HRLAgent:
    def __init__(self, worker_model):
        self.worker = worker_model
        # Usa d_model do worker
        self.manager = HRLManager(input_dim=worker_model.d_model)

    def step(self, context_ids):
        # 1. Obter Estado
        if len(context_ids) > 0:
            last_id = context_ids[-1]
            
            # [FIX] Acessa os pesos via self.params (Modelo V2)
            # Fallback para V1 se necessário
            if hasattr(self.worker, 'params'):
                state_vector = self.worker.params['w_token'][last_id]
            else:
                state_vector = self.worker.token_embedding[last_id]
        else:
            state_vector = np.zeros(self.worker.d_model)

        # 2. Decisão do Gerente
        option_idx = self.manager.select_option(state_vector)
        
        # 3. Execução do Trabalhador
        logits, _ = self.worker.forward(context_ids)
        
        # Pega apenas o último passo do logits (próximo token)
        next_token_logits = logits[-1]
        
        # 4. Viés Hierárquico (Injeção de Intenção)
        next_token_logits = self._apply_manager_bias(next_token_logits, option_idx)
        
        return next_token_logits, option_idx

    def _apply_manager_bias(self, logits, option_idx):
        vocab = self.worker.tokenizer.vocab
        boost = 3.0 
        
        # Clusters de Vocabulário por Intenção
        clusters = {
            0: ["def", "(", ")", ":", "return", ","], # START_FUNC
            1: ["with", "open", "as", "import", "'w'", "'r'"], # I/O
            2: ["write", "read", "=", "+", "texto"]   # LOGIC
        }
        
        target_words = clusters.get(option_idx, [])
        for word in target_words:
            if word in vocab:
                logits[vocab[word]] += boost
        return logits