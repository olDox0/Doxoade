# alfagold/experts/planning_expert.py
import numpy as np
import os
import pickle
from ..core.state_packet import StatePacket

def softmax(x):
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)

class PlanningExpert:
    """
    Expert de Planejamento (Lobo Frontal).
    Agora com capacidade de Aprendizado por Reforço (REINFORCE).
    """
    def __init__(self, d_model=64, vocab_size=2000, num_options=3):
        self.d_model = d_model
        self.num_options = num_options
        self.vocab_size = vocab_size
        self.state_dim = 6 
        
        # Pesos da Rede
        self.W_ctx = np.random.randn(d_model, 32) * 0.05
        self.W_state = np.random.randn(self.state_dim, 32) * 0.5 
        self.W_final = np.random.randn(32, num_options) * 0.1
        
        # Bias de Vocabulário
        self.option_bias = np.zeros((num_options, vocab_size), dtype=np.float32)
        
        # Memória de Treino
        self.cache = {}
        self.episode_buffer = []
        self.current_option = 0
        
        self.path = os.path.expanduser("~/.doxoade/moe_planner_v1.pkl")
        self.load()

    def process(self, packet: StatePacket, training=False) -> StatePacket:
        # 1. Recupera Inputs
        ctx_vector = packet.embedding_vector
        if ctx_vector is None: ctx_vector = np.zeros(self.d_model)
            
        mapa = {"INICIO":0, "NOME":1, "ARGS_PRE":2, "ARGS":3, "TRANSICAO":4, "CORPO":5}
        state_idx = mapa.get(packet.syntax_state, 0)
        state_vec = np.zeros(self.state_dim)
        state_vec[min(state_idx, 5)] = 1.0
        
        # 2. Forward
        h_ctx = np.dot(ctx_vector, self.W_ctx)
        h_state = np.dot(state_vec, self.W_state)
        h_comb = np.maximum(0, h_ctx + h_state)
        
        logits = np.dot(h_comb, self.W_final)
        probs = softmax(logits.reshape(1, -1)).flatten()
        
        # 3. Decisão (Exploração se training=True)
        if training and np.random.rand() < 0.2:
            self.current_option = np.random.randint(self.num_options)
        else:
            self.current_option = np.argmax(probs)
            
        packet.current_goal = f"OPTION_{self.current_option}"
        
        # Cache para Backward
        self.cache['ctx'] = ctx_vector
        self.cache['state'] = state_vec
        self.cache['h'] = h_comb
        self.cache['probs'] = probs
        self.cache['action'] = self.current_option
        
        # 4. Injeção de Viés
        bias_vector = self.option_bias[self.current_option]
        if packet.logits is not None:
            # Resize seguro
            if len(bias_vector) != len(packet.logits):
                new_b = np.zeros(len(packet.logits))
                m = min(len(bias_vector), len(packet.logits))
                new_b[:m] = bias_vector[:m]
                bias_vector = new_b
            packet.logits += bias_vector
            
        return packet

    def register_feedback(self, token_id, reward):
        """Registra feedback imediato e atualiza o bias."""
        # Salva passo para treino da rede
        if 'ctx' in self.cache:
            self.episode_buffer.append({
                'ctx': self.cache['ctx'],
                'state': self.cache['state'],
                'h': self.cache['h'],
                'probs': self.cache['probs'],
                'action': self.cache['action'],
                'reward': reward
            })
            
        # Atualiza bias de opção (Hebbian Learning rápido)
        # Se token_id for válido e reward alto, associa token à opção
        if token_id < self.vocab_size:
            lr = 0.05
            delta = np.clip(lr * reward, -0.5, 0.5)
            self.option_bias[self.current_option, token_id] += delta
            # Clip para não explodir
            self.option_bias[self.current_option, token_id] = np.clip(
                self.option_bias[self.current_option, token_id], -5.0, 5.0
            )

    def train_episode(self, lr=0.01):
        """Atualiza os pesos da rede no fim do episódio."""
        if not self.episode_buffer: return 0
        
        total_reward = sum(step['reward'] for step in self.episode_buffer)
        baseline = total_reward / len(self.episode_buffer)
        
        loss_sum = 0
        for step in self.episode_buffer:
            adv = np.clip(step['reward'] - baseline, -2.0, 2.0)
            
            d_logits = step['probs'].copy()
            d_logits[step['action']] -= 1
            d_logits *= -adv
            
            d_W_final = np.outer(step['h'], d_logits)
            
            d_h = np.dot(self.W_final, d_logits)
            d_h[step['h'] <= 0] = 0
            
            d_W_ctx = np.outer(step['ctx'], d_h)
            d_W_state = np.outer(step['state'], d_h)
            
            self.W_final -= lr * d_W_final
            self.W_ctx -= lr * d_W_ctx
            self.W_state -= lr * d_W_state
            
            loss_sum += np.mean(d_logits**2)
            
        self.episode_buffer = []
        return loss_sum

    def save(self):
        # Filtra apenas dados serializáveis
        data = {k:v for k,v in self.__dict__.items() if k in 
                ['W_ctx', 'W_state', 'W_final', 'option_bias']}
        with open(self.path, 'wb') as f: pickle.dump(data, f)
            
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'rb') as f:
                    data = pickle.load(f)
                    self.__dict__.update(data)
                    print("   🧠 [Planner] Memória carregada.")
            except: pass