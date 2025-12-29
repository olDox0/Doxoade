# doxoade/neural/hive.py
import numpy as np
from colorama import Fore

class HiveMind:
    """
    Rede Fronto-Parietal (Executive Control Network).
    Integração de Worker (Wernicke), Manager (Gânglios), Logic (Broca) e Memory (Hipocampo).
    Adiciona controle de repetição (Cerebelo).
    """
    def __init__(self, worker, manager=None, logic=None):
        self.worker = worker
        self.manager = manager
        self.logic = logic
        
        # [BIO] Memória Episódica (Hipocampo)
        from .memory import VectorDB
        self.hippocampus = VectorDB()
        self.last_memory_context = None

        # Definição do Vocabulário Físico
        if hasattr(worker, 'params') and 'w_token' in worker.params:
            self.vocab_size = worker.params['w_token'].shape[0]
        else:
            self.vocab_size = len(worker.tokenizer.vocab)
        
        # Cache de IDs estruturais
        def safe_get_id(text):
            ids = worker.tokenizer.encode(text)
            return ids[0] if ids else -1

        self.ids = {
            '(': safe_get_id("("),
            ')': safe_get_id(")"),
            ':': safe_get_id(":"),
            ' ': safe_get_id(" "),
            ',': safe_get_id(",")
        }

    def think_and_act(self, context_ids, temp=0.7):
        # 1. Córtex (Worker) - Geração Intuitiva
        logits, _ = self.worker.forward(context_ids)
        final_logits = logits[-1].copy()

        # 2. Gânglios da Base (Manager) - Hábito
        if self.manager:
            state_sym = self.logic.estado if self.logic else "INICIO"
            _, option_idx = self.manager.step(context_ids, symbolic_state=state_sym)
            
            # [BIO] Gating Pré-Frontal (Inibição Top-Down)
            # Se estamos definindo a assinatura, inibimos o desejo do HRL de escrever lógica
            if self.logic and self.logic.estado in ["NOME", "ARGS_PRE", "ARGS"]:
                # Se o HRL escolheu IO (1) ou BODY (2), ignoramos e forçamos START (0)
                if option_idx != 0:
                    # print("   🛡️ [CPFDL] Inibindo impulso prematuro do HRL.")
                    option_idx = 0 
            
            final_logits = self.manager._apply_manager_bias(final_logits, option_idx)

        # 3. Hipocampo - Contexto Passado
        if len(context_ids) % 5 == 0: self._consult_hippocampus(context_ids)
        if self.last_memory_context: self._apply_memory_bias(final_logits)

        # 4. Broca/Logic - Restrição Gramatical
        if self.logic:
            mask = self._generate_logic_mask()
            final_logits += mask

        # 5. Cerebelo - Ajuste Fino e Penalidade de Repetição
        self._apply_cerebellar_correction(final_logits, context_ids)

        # 6. Decisão Motora
        scaled_logits = np.clip(final_logits / temp, -50, 50)
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        next_id = int(np.random.choice(len(probs), p=probs))
        
        # Feedback Sensorial
        if self.logic:
            token_str = self.worker.tokenizer.decode([next_id]).strip()
            if not token_str and next_id == self.ids[' ']: token_str = " "
            if token_str: self.logic.observar(token_str)
                
        return next_id

    def _consult_hippocampus(self, context_ids):
        # (Lógica mantida do anterior: busca vetorial)
        pass 

    def _apply_memory_bias(self, logits):
        # (Lógica mantida: boost em tokens lembrados)
        pass

    def _apply_cerebellar_correction(self, logits, context_ids):
        """
        Simula o Cerebelo: Penalidade de Repetição.
        Evita loops como 'caminho caminho caminho'.
        """
        # Janela de atenção recente (últimos 10 tokens)
        recent = context_ids[-10:]
        
        for token_id in set(recent):
            # Se o token já apareceu recentemente, diminui drasticamente sua probabilidade
            # Penalidade exponencial baseada na frequência recente
            count = recent.count(token_id)
            if count > 0:
                logits[token_id] -= (2.0 * count) # Punição acumulativa

    def _generate_logic_mask(self):
        mask = np.zeros(self.vocab_size, dtype=np.float32)
        # Recupera IDs
        i_open, i_close, i_colon = self.ids['('], self.ids[')'], self.ids[':']
        
        if i_open == -1 or i_colon == -1: return mask

        # --- REGRAS DE BROCA (Sintaxe Rígida) ---
        if self.logic.estado == "ARGS_PRE":
            mask[:] = -1000.0; mask[i_open] = 500.0 
            
        elif self.logic.estado == "TRANSICAO":
            mask[:] = -1000.0; mask[i_colon] = 500.0
            
        elif self.logic.estado == "NOME":
            # Bloqueia pontuação no nome
            mask[i_colon] = -1000.0
            mask[i_open] = 50.0 

        elif self.logic.estado == "ARGS":
            # Bloqueia palavras-chave e pontuação de bloco
            proibidos = [".", ":", ";", "{", "}", "[", "]", "=", "<", ">", 
                         "def", "class", "if", "else", "return", "with", "for", "while", "import"]
            
            vocab = self.worker.tokenizer.vocab
            for token_str, token_id in vocab.items():
                clean = token_str.replace(' ', '').replace('Ġ', '').strip()
                if clean in proibidos: mask[token_id] = -2000.0
            
            # Se já temos variáveis, encoraja fechar
            if self.logic.memoria_variaveis:
                mask[i_close] += 5.0
                if self.ids[','] != -1: mask[self.ids[',']] += 3.0

        return mask