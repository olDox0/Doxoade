# alfagold/training/train_mtl.py
import numpy as np
import sys
import os
import time
from colorama import init, Fore, Style

init(autoreset=True)
current = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(current))
if root not in sys.path: sys.path.insert(0, root)

from alfagold.core.transformer import Alfagold
from alfagold.core.math_utils import softmax
from alfagold.core.optimizer import AdamW
from alfagold.training.data_gen_mtl import generate_mtl_data

def train_mtl():
    print(Fore.YELLOW + "🧠 Iniciando Treino Bicameral V2.1 (Stability Fix)...")
    
    # 1. Reset Seguro
    model = Alfagold(vocab_size=2000, d_model=64)
    optimizer = AdamW(model.params, lr=0.0) 
    
    # Inicializa Log Variance com um valor seguro (0.0 -> var=1.0)
    log_vars = np.zeros(2, dtype=np.float32)
    
    var_optimizer_m = np.zeros(2)
    var_optimizer_v = np.zeros(2)
    var_t = 0
    
    raw_data = generate_mtl_data(count=1000)
    full_text = " ".join([d[0] for d in raw_data])
    model.tokenizer.train(full_text, vocab_size=500)
    
    start_time = time.time()
    
    for epoch in range(30):
        # Warmup suave
        lr = 0.001 * min(1.0, (epoch + 1) / 5)
        optimizer.lr = lr
        
        total_loss = 0
        total_token_loss = 0
        total_phase_loss = 0
        
        indices = np.arange(len(raw_data))
        np.random.shuffle(indices)
        
        for idx in indices:
            text, target_phases = raw_data[idx]
            # ... (tokenização igual) ...
            words = text.split()
            token_ids = []; phase_ids = []
            for i, w in enumerate(words):
                ids = model.tokenizer.encode(w)
                token_ids.extend(ids)
                phase_ids.extend([target_phases[i]] * len(ids))
                
            token_ids = np.array(token_ids); phase_ids = np.array(phase_ids)
            if len(token_ids) < 2: continue
            
            x = token_ids[:-1]; y_token = token_ids[1:]; y_phase = phase_ids[1:]
            
            # Forward
            logits_tok, logits_phase, cache = model.forward(x)
            
            # Loss Calculation (Safe)
            N = len(x)
            probs_tok = softmax(logits_tok)
            loss_tok = -np.sum(np.log(probs_tok[np.arange(N), y_token] + 1e-9)) / N
            
            probs_phase = softmax(logits_phase)
            loss_phase = -np.sum(np.log(probs_phase[np.arange(N), y_phase] + 1e-9)) / N
            
            # [FIX] Limita log_vars para evitar explosão (Min -5, Max 5)
            # exp(-(-5)) = 148 (OK) | exp(-(5)) = 0.006 (OK)
            log_vars = np.clip(log_vars, -5.0, 5.0)
            
            precision1 = np.exp(-log_vars[0])
            precision2 = np.exp(-log_vars[1])
            
            loss = (precision1 * loss_tok + log_vars[0]) + (precision2 * loss_phase + log_vars[1])
            
            # Gradients
            d_tok = probs_tok; d_tok[np.arange(N), y_token] -= 1; d_tok /= N
            d_tok *= precision1
            
            d_phase = probs_phase; d_phase[np.arange(N), y_phase] -= 1; d_phase /= N
            d_phase *= precision2
            
            # Backward
            # [FIX] Check for NaN antes do update
            if np.isnan(loss):
                print("⚠️ Loss NaN detectada. Pulando batch.")
                continue
                
            grads = model.backward(d_tok, d_phase, cache)
            optimizer.step(grads)
            
            # Update Variances
            d_log_var = np.array([-0.5 * precision1 * loss_tok + 0.5, 
                                  -0.5 * precision2 * loss_phase + 0.5])
            
            var_t += 1
            # Adam step manual para vars
            var_optimizer_m = 0.9 * var_optimizer_m + 0.1 * d_log_var
            var_optimizer_v = 0.999 * var_optimizer_v + 0.001 * (d_log_var**2)
            m_hat = var_optimizer_m / (1 - 0.9**var_t)
            v_hat = var_optimizer_v / (1 - 0.999**var_t)
            log_vars -= 0.01 * m_hat / (np.sqrt(v_hat) + 1e-8)
            
            total_loss += loss_tok 
            total_token_loss += loss_tok
            total_phase_loss += loss_phase
            
        avg_loss = total_loss / len(raw_data)
        elapsed = time.time() - start_time
        sigma1 = np.exp(log_vars[0])**0.5
        sigma2 = np.exp(log_vars[1])**0.5
        
        print(f"Ep {epoch+1:02d}: Loss {avg_loss:.4f} | σ_Tok {sigma1:.2f} σ_Ph {sigma2:.2f} ({elapsed:.1f}s)")
        start_time = time.time()
        
    model.save(os.path.expanduser("~/.doxoade/alfagold_v1.pkl"))
    print(Fore.GREEN + "💾 Modelo Bicameral Salvo.")

if __name__ == "__main__":
    train_mtl()