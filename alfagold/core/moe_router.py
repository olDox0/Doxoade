# alfagold/core/moe_router.py
"""
MoE Router (Gating Network).
Responsável por distribuir a carga cognitiva entre os experts disponíveis.
"""
import numpy as np

def softmax(x):
    """Função Softmax estável."""
    # Subtrai o max para evitar overflow exponencial
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)

class MoERouter:
    def __init__(self, input_dim, num_experts):
        # Pesos da rede de roteamento (Gating Network)
        self.W_gate = np.random.randn(input_dim, num_experts) * 0.1
        
    def route(self, state_vector):
        """
        Gating Network.
        Retorna pesos para cada expert (Softmax).
        """
        # Projeção linear
        logits = np.dot(state_vector, self.W_gate)
        # Normalização probabilística
        weights = softmax(logits.reshape(1, -1)).flatten()
        
        # Hard Routing (escolhe apenas o Top-1 ou Top-K)
        # Soft Routing (média ponderada de todos)
        # Vamos começar com Soft Routing
        return weights