# doxoade/neural/hrl.py
import numpy as np
import os
import pickle
from .core import softmax

class HRLManager:
    """
    HRL Manager v4.0 (The Maestro).
    Arquitetura focada em Estado. O sinal simbólico tem via expressa (Skip Connection).
    """
    def __init__(self, input_dim=64, vocab_size=2000, num_options=3):
        self.input_dim = input_dim
        self.num_options = num_options
        self.vocab_size = vocab_size
        self.state_dim = 6 # INICIO, NOME, ARGS_PRE, ARGS, TRANSICAO, CORPO
        
        # Rede Principal (Contexto -> Opção)
        self.W_ctx = np.random.randn(input_dim, 32) * 0.05
        
        # Rede de Estado (Estado -> Opção) - PESOS MAIORES INICIAIS
        # Isso atua como um "Instinto" base
        self.W_state = np.random.randn(self.state_dim, 32) * 0.5 
        
        # Camada de Combinação
        self.W_final = np.random.randn(32, num_options) * 0.1
        
        # Bias de Opção (Vocabulário)
        self.option_embeddings = np.zeros((num_options, vocab_size), dtype=np.float32)
        
        self.cache = {}
        self.episode_buffer = [] 
        self.current_option = 0

    def forward(self, token_vector, state_idx):
        # 1. Processa Contexto (Semântica)
        h_ctx = np.dot(token_vector, self.W_ctx)
        
        # 2. Processa Estado (Estrutura) - One Hot Manual
        state_vec = np.zeros(self.state_dim)
        idx = min(state_idx, self.state_dim - 1)
        state_vec[idx] = 1.0
        
        h_state = np.dot(state_vec, self.W_state)
        
        # 3. Fusão (Soma os sinais)
        # ReLU
        h_combined = np.maximum(0, h_ctx + h_state)
        
        # 4. Decisão
        logits = np.dot(h_combined, self.W_final)
        
        # Clip para estabilidade
        logits = np.clip(logits, -50, 50)
        probs = softmax(logits.reshape(1, -1)).flatten()
        
        # Cache para treino
        self.cache['token_vec'] = token_vector
        self.cache['state_vec'] = state_vec
        self.cache['h_combined'] = h_combined
        self.cache['probs'] = probs
        
        return probs

    def select_option(self, token_vector, state_idx, epsilon=0.1):
        probs = self.forward(token_vector, state_idx)
        
        # Fallback NaN
        if np.isnan(probs).any(): probs = np.ones(self.num_options) / self.num_options

        if np.random.rand() < epsilon:
            option = np.random.randint(self.num_options)
        else:
            option = np.argmax(probs)
            
        self.current_option = option
        self.cache['last_action'] = option
        return option

    def register_step(self, reward):
        # Salva snapshot para o buffer
        if 'token_vec' in self.cache:
            self.episode_buffer.append({
                'token_vec': self.cache['token_vec'],
                'state_vec': self.cache['state_vec'],
                'h': self.cache['h_combined'],
                'probs': self.cache['probs'],
                'action': self.cache['last_action'],
                'reward': reward
            })

    def train_episode(self, lr=0.01):
        if not self.episode_buffer: return 0
        
        # Baseline simples
        rewards = [s['reward'] for s in self.episode_buffer]
        avg_reward = np.mean(rewards)
        
        loss_sum = 0
        
        for step in self.episode_buffer:
            advantage = step['reward'] - avg_reward
            advantage = np.clip(advantage, -2.0, 2.0)
            
            # Gradiente Logits
            d_logits = step['probs'].copy()
            d_logits[step['action']] -= 1
            d_logits *= -advantage
            
            # Backprop W_final
            d_W_final = np.outer(step['h'], d_logits)
            
            # Backprop Hidden (ReLU)
            d_h = np.dot(self.W_final, d_logits)
            d_h[step['h'] <= 0] = 0
            
            # Backprop Ramos (State e Context)
            # Como h = h_ctx + h_state, o gradiente flui igual para ambos
            d_W_ctx = np.outer(step['token_vec'], d_h)
            d_W_state = np.outer(step['state_vec'], d_h)
            
            # Updates
            self.W_final -= lr * d_W_final
            self.W_ctx -= lr * d_W_ctx
            self.W_state -= lr * d_W_state # Esse deve aprender rápido!
            
            loss_sum += np.sum(d_logits**2)

        self.episode_buffer = []
        return loss_sum

    def update_option_bias(self, option_idx, token_id, reward, lr=0.05):
        if token_id >= self.vocab_size: return
        delta = np.clip(lr * reward, -0.5, 0.5)
        self.option_embeddings[option_idx, token_id] += delta
        self.option_embeddings[option_idx, token_id] = np.clip(
            self.option_embeddings[option_idx, token_id], -5.0, 5.0
        )

class HRLAgent:
    def __init__(self, worker_model):
        self.worker = worker_model
        if hasattr(worker_model, 'params') and 'w_token' in worker_model.params:
            vocab_size = worker_model.params['w_token'].shape[0]
            d_model = worker_model.d_model
        else:
            vocab_size = len(worker_model.tokenizer.vocab)
            d_model = 64
            
        self.manager = HRLManager(input_dim=d_model, vocab_size=vocab_size)
        self.path = os.path.expanduser("~/.doxoade/hrl_manager_v4.pkl") # V4
        self.load()

    def step(self, context_ids, symbolic_state="INICIO", training=False):
        # Mapeamento Estendido
        mapa = {"INICIO":0, "NOME":1, "ARGS_PRE":2, "ARGS":3, "TRANSICAO":4, "CORPO":5}
        state_idx = mapa.get(symbolic_state, 0)

        # Context Embedding
        window = 5
        if len(context_ids) > 0:
            ids_to_embed = context_ids[-window:]
            if hasattr(self.worker, 'params'):
                vecs = self.worker.params['w_token'][ids_to_embed]
            else:
                vecs = self.worker.token_embedding[ids_to_embed]
            # Normaliza para reduzir ruído
            token_vector = np.mean(vecs, axis=0)
            norm = np.linalg.norm(token_vector)
            if norm > 0: token_vector /= norm
        else:
            token_vector = np.zeros(self.manager.input_dim)

        # Decisão
        eps = 0.2 if training else 0.0
        option_idx = self.manager.select_option(token_vector, state_idx, epsilon=eps)
        
        # Worker Forward
        logits, _ = self.worker.forward(context_ids)
        
        # Bias
        bias = self.manager.option_embeddings[option_idx]
        vocab_len = len(logits[-1])
        if len(bias) != vocab_len:
             new_bias = np.zeros(vocab_len)
             m = min(len(bias), vocab_len)
             new_bias[:m] = bias[:m]
             bias = new_bias
             
        return logits[-1] + bias, option_idx

    def register_feedback(self, token_id, reward):
        self.manager.register_step(reward)
        if token_id < self.manager.vocab_size:
            self.manager.update_option_bias(self.manager.current_option, token_id, reward)

    def end_episode(self):
        return self.manager.train_episode()

    def save(self):
        with open(self.path, 'wb') as f: pickle.dump(self.manager, f)
            
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'rb') as f:
                    saved = pickle.load(f)
                    # Verifica compatibilidade V4
                    if hasattr(saved, 'state_dim') and saved.state_dim == 6:
                        self.manager = saved
                        print("   🧠 Maestro (HRL v4) carregado.")
                    else:
                        print("⚠️ [HRL] Versão antiga detectada. Iniciando Maestro v4.")
            except: pass