# alfagold/hive/hive_mind.py
import numpy as np
from colorama import Fore

from ..core.state_packet import StatePacket
from ..core.moe_router import MoERouter
from ..experts.generator_expert import GeneratorExpert
from ..experts.syntax_expert import SyntaxExpert

class HiveMindMoE:
    def __init__(self):
        # 1. Experts
        self.generator = GeneratorExpert()
        
        # O SyntaxExpert precisa do tokenizer do modelo para saber os IDs
        self.syntax = SyntaxExpert(self.generator.model.tokenizer)
        
        # 2. Roteador
        self.router = MoERouter(input_dim=self.generator.model.d_model, num_experts=2)
        
    def generate_step(self, packet: StatePacket, temp=0.7):
        """Executa um passo de tempo cognitivo."""
        
        # --- FASE 1: GERAÇÃO (Excitação) ---
        packet = self.generator.process(packet)
        final_logits = packet.logits.copy()
        
        # --- FASE 2: INIBIÇÃO (Sintaxe) ---
        # Pede ao SyntaxExpert uma máscara baseada no estado atual
        # Passamos o shape atual dos logits para garantir alinhamento
        mask = self.syntax.get_inhibition_mask(final_logits.shape[0])
        packet.inhibition_mask = mask
        
        # Fusão Neural
        final_logits += mask
        
        # --- FASE 3: DECISÃO (Amostragem) ---
        scaled_logits = np.clip(final_logits / temp, -50, 50)
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        next_id = int(np.random.choice(len(probs), p=probs))
        
        # --- FASE 4: FEEDBACK (Atualização de Estado) ---
        packet.token_ids.append(next_id)
        token_str = self.generator.decode(next_id)
        packet.generated_token = token_str
        
        # O SyntaxExpert observa o que foi decidido para atualizar sua máquina de estados
        self.syntax.observe(token_str)
        
        return packet, token_str

    def run_sequence(self, prompt, length=50):
        packet = StatePacket(input_text=prompt)
        print(f"🧠 [HiveMoE] Prompt: {prompt}")
        
        # Sincroniza o SyntaxExpert com o prompt inicial
        # (Lê o prompt token por token para setar o estado correto, ex: NOME)
        initial_ids = self.generator.model.tokenizer.encode(prompt)
        for tid in initial_ids:
            t_str = self.generator.decode(tid)
            self.syntax.observe(t_str)
            
        full_text = ""
        
        for _ in range(length):
            packet, token = self.generate_step(packet)
            if "ENDMARKER" in token: break
            print(".", end="", flush=True)
            full_text += token
            
        print("\n✅ Concluído.")
        return full_text