# alfagold/experts/syntax_expert.py
import numpy as np

class SyntaxExpert:
    """
    Syntax Expert v20.0 (Context Flow).
    Adiciona regras rígidas de sequenciamento para keywords (with -> open).
    """
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.vocab_size = len(tokenizer.vocab)
        
        # Estado Interno
        self.memoria_variaveis = set()
        self.pilha_parenteses = 0 
        self.estado = "INICIO" 
        self.ultimo_token = ""
        self.penultimo_token = ""
        self.assinatura_concluida = False
        
        self.ids = self._map_structural_tokens()
        
        self.keywords = ["def", "return", "if", "else", "with", "open", "as", "pass", "import"]

    def _map_structural_tokens(self):
        target_chars = {"(": "open", ")": "close", ":": "colon", ",": "comma", " ": "space"}
        mapped = {v: -1 for v in target_chars.values()}
        for char, name in target_chars.items():
            ids = self.tokenizer.encode(char)
            if ids: mapped[name] = ids[0]
        return mapped

    def reset(self):
        self.__init__(self.tokenizer)

    def observe(self, token_str):
        self.observar(token_str)

    def observar(self, token):
        token = token.strip()
        if not token: return
        
        self.penultimo_token = self.ultimo_token
        self.ultimo_token = token
        
        if token == "def": 
            self.estado = "NOME"
            self.assinatura_concluida = False
            self.pilha_parenteses = 0
            
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
                    
        if self.estado == "ARGS" and token.isidentifier() and token not in self.keywords:
            self.memoria_variaveis.add(token)

    def get_inhibition_mask(self, current_logits_shape):
        mask = np.zeros(current_logits_shape, dtype=np.float32)
        i_open = self.ids['open']
        i_colon = self.ids['colon']
        
        if i_open == -1: return mask

        # Assinatura
        if self.estado == "ARGS_PRE":
            mask[:] = -1000.0; mask[i_open] = 500.0 
        elif self.estado == "TRANSICAO":
            mask[:] = -1000.0; mask[i_colon] = 500.0
        elif self.estado == "NOME":
            mask[self.ids['colon']] = -1000.0
            mask[i_open] = 50.0 

        # [NOVO] Regras de Fluxo no Corpo
        if self.estado == "CORPO":
            # Se o último foi 'with', o próximo TEM que ser 'open'
            if self.ultimo_token == "with":
                # Penaliza tudo que não for 'open'
                # (Idealmente, acharíamos o ID de open, mas como é variável no BPE, 
                # deixamos a validação simbólica filtrar no passo de amostragem)
                pass

        return mask

    def validar(self, token):
        token = token.strip()
        if not token: return True, "Espaço"

        # 1. Assinatura (Igual v19)
        if not self.assinatura_concluida:
            if self.estado == "ARGS_PRE" and "(" not in token: return False, "Esperando '('"
            if self.estado == "TRANSICAO" and ":" not in token: return False, "Esperando ':'"
            if self.estado == "NOME" and any(c in ":.," for c in token): return False, "Pontuação no nome"

        # 2. Argumentos
        if self.estado == "ARGS":
            if token in self.keywords: return False, "Keyword em argumento"
            last_was_var = self.ultimo_token.isidentifier() and self.ultimo_token not in self.keywords
            if last_was_var and token.isidentifier() and token not in self.keywords:
                return False, "Variáveis adjacentes"

        # 3. Corpo (Regras de Sequenciamento)
        if self.estado == "CORPO":
            # Regra do WITH
            if self.ultimo_token == "with":
                if "open" not in token: return False, "Esperando 'open' após 'with'"
            
            # Regra do OPEN
            if self.ultimo_token == "open":
                if "(" not in token: return False, "Esperando '(' após 'open'"
                
            # Regra do AS
            if self.ultimo_token == "as":
                if not token.isidentifier(): return False, "Esperando variável após 'as'"

            # Início de bloco
            if self.ultimo_token.endswith(":"):
                if token in [".", ",", ")", "]", "}"] or token == "(": return False, "Início inválido"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        if self.estado == "ARGS" and self.ultimo_token.isidentifier() and self.ultimo_token not in self.keywords: return ")"
        
        # Sugestões de Fluxo
        if self.estado == "CORPO":
            if self.ultimo_token.endswith(":"): return "with"
            if self.ultimo_token == "with": return "open" # Força o open
            if self.ultimo_token == "open": return "("
            
        return None