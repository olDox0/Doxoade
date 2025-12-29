# alfagold/hive/hive_mind.py
import numpy as np
from ..core.state_packet import StatePacket
from ..core.moe_router import MoERouter

# Importando os Experts
from ..experts.generator_expert import GeneratorExpert
from ..experts.syntax_expert import SyntaxExpert   # Antigo Logic/Arquiteto (renomear/adaptar se necessário)
# from ..experts.memory_expert import MemoryExpert # Futuro

class HiveMindMoE:
    def __init__(self):
        # 1. Hardware
        self.generator = GeneratorExpert()
        # self.syntax = SyntaxExpert() # Habilitar quando migrado
        
        # 2. Roteador (Gating Network)
        # Input: Dimensão do modelo (64)
        # Outputs: 2 Experts (Generator, Syntax - por enquanto)
        self.router = MoERouter(input_dim=self.generator.model.d_model, num_experts=2)
        
    def generate_step(self, packet: StatePacket, temp=0.7):
        """
        Executa um passo de tempo cognitivo.
        """
        # 1. Roteamento: Quem deve trabalhar agora?
        weights = [1.0, 0.0]
        if packet.embedding_vector is not None:
             weights = self.router.route(packet.embedding_vector)
             # [FIX] Uso da variável para silenciar o linter e preparar o futuro
             # print(f"DEBUG: Router Weights: {weights}") 
        
        # 2. Execução dos Experts (Soft Mixing)
        # Por enquanto, focamos no Generator como motor principal
        packet = self.generator.process(packet)
        final_logits = packet.logits.copy()
        
        # Aqui entraria a mistura com outros experts baseada nos 'weights'
        # Ex: if weights[1] > 0.5: packet = self.syntax.process(packet) ...
        
        # 3. Decisão (Amostragem)
        scaled_logits = np.clip(final_logits / temp, -50, 50)
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        next_id = int(np.random.choice(len(probs), p=probs))
        
        # 4. Atualização do Estado
        packet.token_ids.append(next_id)
        token_str = self.generator.decode(next_id)
        packet.generated_token = token_str
        
        return packet, token_str

    def run_sequence(self, prompt, length=50):
        """Loop de geração completo."""
        packet = StatePacket(input_text=prompt)
        print(f"🧠 [HiveMoE] Prompt: {prompt}")
        
        full_text = ""
        
        for _ in range(length):
            packet, token = self.generate_step(packet)
            
            # Critério de Parada Simples
            if "ENDMARKER" in token: break
            
            print(".", end="", flush=True)
            full_text += token
            
        print("\n✅ Concluído.")
        return full_text