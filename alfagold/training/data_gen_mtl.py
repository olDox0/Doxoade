# alfagold/training/data_gen_mtl.py
import random

# Fases: 0:INICIO, 1:NOME, 2:ARGS, 3:TRANSICAO, 4:CORPO, 5:IO
PHASES = {"INICIO":0, "NOME":1, "ARGS":2, "TRANSICAO":3, "CORPO":4}

def generate_mtl_data(count=1000):
    """Gera pares (Código, Lista_de_Fases) para treino supervisionado."""
    dataset = []
    
    for _ in range(count):
        # Template: def nome(arg): with open...
        f_name = random.choice(["salvar", "ler", "gravar", "logar"])
        arg = random.choice(["arquivo", "path", "caminho"])
        mode = random.choice(["'w'", "'r'", "'a'"])
        
        # Constrói token a token com sua fase
        tokens = []
        phases = []
        
        # def
        tokens.append("def"); phases.append(PHASES["INICIO"])
        
        # nome
        tokens.append(f_name); phases.append(PHASES["NOME"])
        
        # (arg)
        tokens.append("("); phases.append(PHASES["ARGS"])
        tokens.append(arg); phases.append(PHASES["ARGS"])
        tokens.append(")"); phases.append(PHASES["ARGS"])
        
        # :
        tokens.append(":"); phases.append(PHASES["TRANSICAO"])
        
        # Corpo I/O
        tokens.append("with"); phases.append(PHASES["CORPO"])
        tokens.append("open"); phases.append(PHASES["CORPO"])
        tokens.append("("); phases.append(PHASES["CORPO"])
        tokens.append(arg); phases.append(PHASES["CORPO"])
        tokens.append(","); phases.append(PHASES["CORPO"])
        tokens.append(mode); phases.append(PHASES["CORPO"])
        tokens.append(")"); phases.append(PHASES["CORPO"])
        tokens.append("as"); phases.append(PHASES["CORPO"])
        tokens.append("f"); phases.append(PHASES["CORPO"])
        tokens.append(":"); phases.append(PHASES["CORPO"])
        tokens.append("pass"); phases.append(PHASES["CORPO"])
        
        full_text = " ".join(tokens)
        dataset.append((full_text, phases))
        
    return dataset