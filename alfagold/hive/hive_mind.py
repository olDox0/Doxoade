# alfagold/hive/hive_mind.py
import numpy as np
from colorama import Fore

from ..core.state_packet import StatePacket
from ..core.moe_router import MoERouter
from ..experts.generator_expert import GeneratorExpert
from ..experts.syntax_expert import SyntaxExpert
from ..experts.planning_expert import PlanningExpert
from ..experts.refinement_expert import RefinementExpert
# [NOVO]
from ..experts.reward_expert import RewardExpert

class HiveMindMoE:
    def __init__(self):
        # Experts
        self.generator = GeneratorExpert()
        self.syntax = SyntaxExpert(self.generator.model.tokenizer)
        self.planner = PlanningExpert(
            d_model=self.generator.model.d_model,
            vocab_size=len(self.generator.model.tokenizer.vocab)
        )
        self.cerebellum = RefinementExpert()
        # [NOVO] O Crítico Interno
        self.rewarder = RewardExpert(self.generator.model.tokenizer)
        
        self.router = MoERouter(input_dim=self.generator.model.d_model, num_experts=3)

    def generate_step(self, packet: StatePacket, temp=0.7):
        # ... (Mantém a lógica de geração idêntica à versão anterior) ...
        # (Copiando a lógica para garantir que o arquivo fique completo)
        packet = self.generator.process(packet)
        packet.syntax_state = self.syntax.estado
        packet = self.planner.process(packet)
        
        final_logits = packet.logits.copy()
        mask = self.syntax.get_inhibition_mask(final_logits.shape[0])
        final_logits += mask
        
        scaled_logits = np.clip(final_logits / temp, -50, 50)
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        next_id = None
        for _ in range(10):
            cand_id = int(np.random.choice(len(probs), p=probs))
            token_str = self.generator.decode(cand_id).strip()
            if not token_str: token_str = " "
            valido, _ = self.syntax.validar(token_str)
            if valido:
                next_id = cand_id
                self.syntax.observe(token_str)
                break
            else:
                probs[cand_id] = 0
                s = np.sum(probs)
                if s > 0: probs /= s
                else: break
        
        if next_id is None:
            sug = self.syntax.sugerir_correcao()
            if sug:
                sug_ids = self.generator.model.tokenizer.encode(sug)
                if sug_ids: next_id = sug_ids[0]; self.syntax.observe(sug)
        
        if next_id is None: next_id = int(np.argmax(final_logits))
            
        packet.token_ids.append(next_id)
        packet.generated_token = self.generator.decode(next_id)
        return packet, packet.generated_token

    def run_sequence(self, prompt, length=50, attempts=3):
        """
        Gera múltiplas tentativas e escolhe a melhor (Metacognição).
        """
        best_code = ""
        best_score = -1.0
        
        print(f"🧠 [HiveMoE] Metacognição Ativa (Best of {attempts})")
        
        for i in range(attempts):
            # Reinicia estado para nova tentativa
            packet = StatePacket(input_text=prompt)
            input_ids = self.generator.model.tokenizer.encode(prompt)
            packet.token_ids = list(input_ids)
            
            # Reset do Arquiteto
            self.syntax.reset()
            for tid in input_ids: self.syntax.observe(self.generator.decode(tid))
            
            # Geração (com temperatura variada para explorar)
            # Tentativa 1: Focada (0.1). Tentativa 2/3: Criativa (0.5/0.8)
            current_temp = 0.1 + (i * 0.3)
            raw_text = ""
            
            # print(f"   🤔 Pensando variação #{i+1} (t={current_temp:.1f})...", end="", flush=True)
            
            for _ in range(length):
                packet, token = self.generate_step(packet, temp=current_temp)
                if "ENDMARKER" in token: break
                raw_text += token
            
            # Refinamento (Cerebelo)
            full_candidate = prompt + raw_text
            refined_candidate = self.cerebellum.process(full_candidate)
            
            # Avaliação (Orbitofrontal)
            score = self.rewarder.evaluate(prompt, refined_candidate)
            
            # [FIX] MOSTRAR O PENSAMENTO
            print(f"   🤔 Tentativa #{i+1}: Score {score:.2f} | Len: {len(refined_candidate)}")
            # print(f"      Code: {refined_candidate[:30]}...") # Opcional
            
            if score > best_score:
                best_score = score
                best_code = refined_candidate
                
            # Se achou algo muito bom, para cedo
            if best_score > 0.8: break

        print(f"\n🏆 Melhor Resultado (Score: {best_score:.2f}):")
        return best_code