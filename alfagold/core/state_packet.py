# alfagold/core/state_packet.py
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

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
    
    # 3. Sinais dos Experts
    logits: Optional[np.ndarray] = None           # Sinal Excitátorio (Generator)
    inhibition_mask: Optional[np.ndarray] = None  # Sinal Inibitório (Syntax)
    
    # 4. Saída Final
    generated_token_id: int = -1
    generated_token_str: str = ""
    
    def clone(self):
        from copy import deepcopy
        return deepcopy(self)