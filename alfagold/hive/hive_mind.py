# alfagold/hive/hive_mind.py
import numpy as np
from colorama import Fore

from ..core.state_packet import StatePacket
from ..core.moe_router import MoERouter
from ..experts.generator_expert import GeneratorExpert
from ..experts.syntax_expert import SyntaxExpert
from ..experts.planning_expert import PlanningExpert # [NOVO]

class HiveMindMoE:
    def __init__(self):
        # 1. Experts (Lobos Cerebrais)
        self.generator = GeneratorExpert()
        # O Syntax precisa do tokenizer para saber IDs
        self.syntax = SyntaxExpert(self.generator.model.tokenizer)
        
        # O Planner precisa saber a dimensão do modelo e do vocab
        self.planner = PlanningExpert(
            d_model=self.generator.model.d_model,
            vocab_size=len(self.generator.model.tokenizer.vocab)
        )
        
        # 2. Roteador
        self.router = MoERouter(input_dim=self.generator.model.d_model, num_experts=3)
        
    def generate_step(self, packet: StatePacket, temp=0.7):
        """Executa um passo de tempo cognitivo."""
        
        # --- FASE 1: GERAÇÃO (Wernicke) ---
        packet = self.generator.process(packet)
        # O packet.logits agora tem a probabilidade base (estatística pura)
        
        # --- FASE 2: PLANEJAMENTO (Frontal) ---
        # O Planner olha o estado (Sintaxe + Vetor) e empurra para I/O ou Lógica
        # Antes de chamar, atualizamos o estado sintático no pacote
        packet.syntax_state = self.syntax.estado
        packet = self.planner.process(packet)
        # Agora packet.logits tem Base + Viés do Planner
        
        # --- FASE 3: INIBIÇÃO (Broca) ---
        # O Syntax aplica a máscara de veto (-inf)
        final_logits = packet.logits.copy()
        mask = self.syntax.get_inhibition_mask(final_logits.shape[0])
        packet.inhibition_mask = mask
        final_logits += mask
        
        # --- FASE 4: DECISÃO (Amostragem com Rejeição) ---
        scaled_logits = np.clip(final_logits / temp, -50, 50)
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        next_id = None
        
        # Tentativa de Amostragem Segura
        for _ in range(10):
            cand_id = int(np.random.choice(len(probs), p=probs))
            token_str = self.generator.decode(cand_id).strip()
            
            # Validação Rápida
            if not token_str and cand_id == self.syntax.ids.get('space', -1): token_str = " "
            
            valido, _ = self.syntax.validar(token_str)
            if valido:
                next_id = cand_id
                self.syntax.observe(token_str) # Atualiza máquina de estados
                break
            else:
                # Punição instantânea para re-sorteio
                probs[cand_id] = 0
                s = np.sum(probs)
                if s > 0: probs /= s
                else: break

        # Fallback (Resgate do Arquiteto)
        if next_id is None:
            sug = self.syntax.sugerir_correcao()
            if sug:
                sug_ids = self.generator.model.tokenizer.encode(sug)
                if sug_ids: 
                    next_id = sug_ids[0]
                    self.syntax.observe(sug)

        # Fallback Final (Argmax)
        if next_id is None:
            next_id = int(np.argmax(final_logits))
            # Tenta observar para não perder sincronia
            self.syntax.observe(self.generator.decode(next_id).strip())
        
        # --- FASE 5: FEEDBACK ---
        packet.token_ids.append(next_id)
        token_str = self.generator.decode(next_id)
        packet.generated_token = token_str
        
        return packet, token_str

    def run_sequence(self, prompt, length=50):
        # ... (Mantém igual ao anterior) ...
        # Apenas certifique-se de sincronizar o Syntax no início
        packet = StatePacket(input_text=prompt)
        print(f"🧠 [HiveMoE] Prompt: {prompt}")
        
        # Boot do Syntax e Generator
        input_ids = self.generator.model.tokenizer.encode(prompt)
        packet.token_ids = list(input_ids) # Inicializa histórico
        
        for tid in input_ids:
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