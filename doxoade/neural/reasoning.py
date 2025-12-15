"""
SHERLOCK v2.1 - Reasoning Engine.
Adiciona verificação de Cobertura de Variáveis (todas devem ser usadas).
"""
import re

class Sherlock:
    def __init__(self):
        self.knowledge_base = {
            "soma": ["+"], "add": ["+"], "plus": ["+"],
            "sub": ["-"], "minus": ["-"], "diff": ["-"],
            "mult": ["*"], "times": ["*"], "prod": ["*"],
            "div": ["/"], "split": ["/"]
        }
        self.proibicoes = set()

    def deduzir_requisitos(self, prompt):
        prompt = prompt.lower()
        requisitos = set()
        for key, operators in self.knowledge_base.items():
            if key in prompt:
                for op in operators: requisitos.add(op)
        return list(requisitos)

    def analisar_falha(self, codigo, erro_stdout, erro_stderr):
        """Analisa a falha para banir elementos."""
        # Se falhou no teste lógico (Assert), mas compilou
        if "FALHA_ASSERT" in erro_stdout:
            # Se usou variáveis duplicadas (ex: b + b), bane a duplicação
            # Heurística simples: procurar "x op x"
            tokens = codigo.split()
            for i in range(2, len(tokens)):
                # Se token atual é igual ao anterior do anterior (a + a)
                if tokens[i] == tokens[i-2] and tokens[i].isalnum():
                    padrao_ruim = f"{tokens[i-2]} {tokens[i-1]} {tokens[i]}"
                    self.proibicoes.add(padrao_ruim)
                    return f"Padrão repetitivo detectado e banido: '{padrao_ruim}'"
            
            return "Lógica incorreta (Operador ou ordem)."
        
        if "NameError" in erro_stderr:
            m = re.search(r"name '(.+?)' is not defined", erro_stderr)
            if m:
                var_name = m.group(1)
                self.proibicoes.add(var_name)
                return f"Variável inexistente '{var_name}'."

        return "Erro estrutural não conclusivo."

    def verificar_analogia(self, codigo_gerado, requisitos):
        # 1. Requisitos de Operador
        for req in requisitos:
            if req not in codigo_gerado:
                return False, f"Falta o operador deduzido '{req}'"
        
        # 2. Proibições Empíricas (Aprendidas com falhas)
        for proibido in self.proibicoes:
            if proibido in codigo_gerado:
                return False, f"Contém padrão proibido: '{proibido}'"

        # 3. NOVA REGRA: Cobertura de Argumentos
        # Se definiu (a, b), tem que usar a e b.
        if "def " in codigo_gerado and ":" in codigo_gerado:
            try:
                # Extrai argumentos: entre '(' e ')'
                args_str = codigo_gerado.split('(')[1].split(')')[0]
                args = [a.strip() for a in args_str.split(',') if a.strip()]
                
                # Extrai corpo: depois de ':'
                corpo = codigo_gerado.split(':')[1]
                
                # Verifica se cada argumento está no corpo
                for arg in args:
                    # Busca o argumento cercado por espaços ou fim de linha para evitar falso positivo
                    # (ex: não achar 'a' dentro de 'val')
                    if not re.search(rf"\b{arg}\b", corpo):
                        return False, f"Variável '{arg}' foi definida mas ignorada no cálculo."
            except Exception:
                pass # Se falhar o parse manual, deixa passar (o Arquiteto cuida da sintaxe)

        return True, "OK"