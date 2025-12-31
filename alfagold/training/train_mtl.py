# alfagold/training/train_mtl.py
import numpy as np
import sys
import os
import time
from colorama import init, Fore

init(autoreset=True)
current = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(current))
if root not in sys.path: sys.path.insert(0, root)

from alfagold.core.transformer import Alfagold, softmax
from alfagold.core.optimizer import AdamW # CORRETO
from alfagold.training.data_gen_mtl import generate_mtl_data

def train_mtl():
    print(Fore.YELLOW + "🧠 Iniciando Treino Bicameral (Texto + Consciência)...")
    
    # 1. Configuração
    # Reset do modelo para pegar os novos pesos W_phase
    model = Alfagold(vocab_size=2000, d_model=64)
    optimizer = AdamW(model.params, lr=0.005) # LR um pouco maior para convergir as duas tarefas
    
    # 2. Dados
    raw_data = generate_mtl_data(count=500)
    
    # Treina tokenizer rápido
    full_text = " ".join([d[0] for d in raw_data])
    model.tokenizer.train(full_text, vocab_size=500)
    
    start_time = time.time()
    
    for epoch in range(30):
        total_loss = 0
        total_token_loss = 0
        total_phase_loss = 0
        
        for text, target_phases in raw_data:
            # Tokeniza
            # Nota: Precisamos alinhar os tokens BPE com as fases manuais.
            # Hack simplificado: Assumimos mapeamento 1-1 para este dataset controlado
            # (Em produção, precisaríamos projetar as fases nos tokens BPE)
            
            # Vamos tokenizar palavra por palavra para manter alinhamento com data_gen
            words = text.split()
            token_ids = []
            phase_ids = []
            
            for i, w in enumerate(words):
                # Codifica a palavra (pode gerar multiplos tokens BPE)
                ids = model.tokenizer.encode(w)
                token_ids.extend(ids)
                # Repete a fase para cada subt-token
                phase_ids.extend([target_phases[i]] * len(ids))
                
            token_ids = np.array(token_ids)
            phase_ids = np.array(phase_ids)
            
            if len(token_ids) < 2: continue
            
            # Inputs e Targets
            x = token_ids[:-1]
            y_token = token_ids[1:]
            y_phase = phase_ids[1:] # A fase do próximo token
            
            # --- CICLO MTL ---
            
            # 1. Forward
            logits_tok, logits_phase, cache = model.forward(x)
            
            # 2. Loss Token (Cross Entropy)
            N = len(x)
            probs_tok = softmax(logits_tok)
            correct_tok = probs_tok[np.arange(N), y_token]
            loss_tok = -np.sum(np.log(correct_tok + 1e-9)) / N
            
            # 3. Loss Phase (Cross Entropy)
            probs_phase = softmax(logits_phase)
            correct_phase = probs_phase[np.arange(N), y_phase]
            loss_phase = -np.sum(np.log(correct_phase + 1e-9)) / N
            
            # Loss Total (Soma Ponderada)
            loss = loss_tok + (loss_phase * 0.5) # Foco principal no texto
            
            # 4. Gradientes
            d_tok = probs_tok
            d_tok[np.arange(N), y_token] -= 1
            d_tok /= N
            
            d_phase = probs_phase
            d_phase[np.arange(N), y_phase] -= 1
            d_phase /= N
            d_phase *= 0.5 # Peso da loss
            
            # 5. Backward & Update
            grads = model.backward(d_tok, d_phase, cache)
            optimizer.step(grads)
            
            total_loss += loss
            total_token_loss += loss_tok
            total_phase_loss += loss_phase
            
        avg_loss = total_loss / len(raw_data)
        print(f"Ep {epoch+1}: Total {avg_loss:.3f} | Tok {total_token_loss/len(raw_data):.3f} | Phase {total_phase_loss/len(raw_data):.3f}")
        
    model.save(os.path.expanduser("~/.doxoade/alfagold_v1.pkl"))
    print(Fore.GREEN + "💾 Modelo Bicameral Salvo.")

if __name__ == "__main__":
    train_mtl()