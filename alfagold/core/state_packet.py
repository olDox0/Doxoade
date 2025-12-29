# alfagold/core/state_packet.py
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class StatePacket:
    """
    O Neurotransmissor Digital.
    Carrega todo o contexto cognitivo de um passo de tempo.
    """
    # 1. Entrada Bruta
    input_text: str = ""
    token_ids: List[int] = field(default_factory=list)
    
    # 2. Estado Neural (Latente)
    embedding_vector: Optional[np.ndarray] = None # (D_model,)
    attention_focus: Optional[np.ndarray] = None  # (Seq_len,)
    
    # 3. Estado Simbólico (Broca)
    syntax_state: str = "INICIO" # NOME, ARGS, CORPO
    syntax_stack: List[str] = field(default_factory=list) # Pilha de parenteses
    
    # 4. Estado Executivo (PFC)
    intent: str = "GENERIC" # I/O, MATH, LOGIC
    current_goal: str = ""
    plan_steps: List[str] = field(default_factory=list)
    
    # 5. Memória (Hipocampo)
    retrieved_memories: List[str] = field(default_factory=list)
    
    # 6. Saída e Feedback
    generated_token: str = ""
    logits: Optional[np.ndarray] = None
    reward: float = 0.0
    
    def clone(self):
        """Cria uma cópia para preservar histórico."""
        # Implementação rasa para performance, profunda se necessário
        from copy import deepcopy
        return deepcopy(self)