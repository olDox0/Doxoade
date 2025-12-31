# alfagold/experts/syntax_expert.py
import numpy as np

class SyntaxExpert:
    """
    Expert Simbólico (Broca).
    Gera máscaras de inibição para garantir a gramática.
    """
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.vocab_size = len(tokenizer.vocab)
        
        # Estado Interno
        self.pilha_parenteses = 0 
        self.estado = "INICIO" 
        self.ultimo_token = ""
        self.assinatura_concluida = False
        
        # Cache de IDs (Mapeamento Robusto)
        self.ids = self._map_structural_tokens()
        
        self.keywords = ["def", "return", "if", "else", "with", "open", "as", "pass", "import"]
        self.pontuacao = ["(", ")", ":", ",", "."]

    def _map_structural_tokens(self):
        """Encontra os IDs reais dos tokens de pontuação."""
        target_chars = {"(": "open", ")": "close", ":": "colon", ",": "comma"}
        mapped = {v: -1 for v in target_chars.values()}
        
        # Busca exata
        for char, name in target_chars.items():
            ids = self.tokenizer.encode(char)
            if ids: mapped[name] = ids[0]
            
        return mapped

    def reset(self):
        self.__init__(self.tokenizer)

    def observe(self, token_str):
        """Atualiza o estado mental baseado no token escolhido."""
        token = token_str.strip()
        if not token: return
        self.ultimo_token = token
        
        # Máquina de Estados
        if token == "def": 
            self.estado = "NOME"
            self.assinatura_concluida = False
            return

        if self.estado == "NOME" and token.isidentifier() and token not in self.keywords:
            self.estado = "ARGS_PRE"
            return

        for char in token:
            if char == "(": 
                self.pilha_parenteses += 1
                if self.estado in ["NOME", "ARGS_PRE"]: self.estado = "ARGS"
            elif char == ")": 
                if self.pilha_parenteses > 0: self.pilha_parenteses -= 1
                if self.pilha_parenteses == 0 and self.estado == "ARGS": 
                    self.estado = "TRANSICAO" 
            elif char == ":": 
                if self.estado == "TRANSICAO": 
                    self.estado = "CORPO"
                    self.assinatura_concluida = True

    def get_inhibition_mask(self, current_logits_shape):
        """Gera o vetor de inibição (Mask)."""
        # Garante que a máscara bata com o tamanho do vetor de logits do modelo
        mask = np.zeros(current_logits_shape, dtype=np.float32)
        
        i_open = self.ids['open']
        i_close = self.ids['close']
        i_colon = self.ids['colon']
        
        # Se não mapeou, não arrisca bloquear
        if i_open == -1 or i_colon == -1: return mask

        # --- REGRAS DE BLOQUEIO ---
        if self.estado == "ARGS_PRE":
            mask[:] = -1000.0; mask[i_open] = 500.0 
            
        elif self.estado == "TRANSICAO":
            mask[:] = -1000.0; mask[i_colon] = 500.0
            
        elif self.estado == "NOME":
            # Bloqueia pontuação no nome
            mask[i_colon] = -1000.0
            mask[i_open] = 50.0 

        elif self.estado == "ARGS":
            # Bloqueia palavras-chave e pontuação de bloco
            proibidos = [".", ":", ";", "{", "}", "[", "]", "=", "<", ">", 
                         "def", "class", "if", "else", "return", "with", "for", "while", "import"]
            
            # Penalidade varredura (Lento, mas seguro para V1)
            # Numa versão otimizada, cachearíamos os IDs proibidos no init
            for token_str, token_id in self.tokenizer.vocab.items():
                if token_id < len(mask):
                    clean = token_str.replace(' ', '').replace('Ġ', '').strip()
                    if clean in proibidos: mask[token_id] = -2000.0
            
            # Se já temos variáveis (heurística simples), encoraja fechar
            if self.pilha_parenteses > 0:
                mask[i_close] += 5.0

        return mask