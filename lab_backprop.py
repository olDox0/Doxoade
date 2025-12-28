# lab_backprop.py
import numpy as np
import time
import sys
import os
from colorama import init, Fore

# Garante import
sys.path.insert(0, os.path.abspath('.'))

from doxoade.neural.alfagold.model import Alfagold
from doxoade.neural.alfagold.optimizer import AdamW

init(autoreset=True)

def train_sanity_check():
    print(Fore.YELLOW + "🧪 [ALFAGOLD] Teste de Sanidade do Backpropagation...\n")
    
    # 1. Configuração Miniatura
    model = Alfagold(vocab_size=100, d_model=16, max_len=10)
    optimizer = AdamW(model.params, lr=0.01)
    
    # Dados de treino (Overfitting proposital)
    # Ensinar a sequência: 1, 2, 3, 4, 5
    data = [1, 2, 3, 4, 5]
    inputs = np.array(data[:-1]) # [1, 2, 3, 4]
    targets = np.array(data[1:]) # [2, 3, 4, 5]
    
    print(f"   Treinando sequência: {inputs} -> {targets}")
    
    initial_loss = 0
    final_loss = 0
    
    # Loop de Treino
    start = time.time()
    for i in range(50):
        # 1. Forward
        logits, cache = model.forward(inputs, training=True)
        
        # 2. Loss (Cross Entropy)
        # Pega a probabilidade do token correto
        # Logits: (4, 100) -> Target: (4,)
        rows = np.arange(len(targets))
        
        # Softmax numérico
        exps = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exps / np.sum(exps, axis=1, keepdims=True)
        
        correct_probs = probs[rows, targets]
        loss = -np.sum(np.log(correct_probs + 1e-9)) / len(targets)
        
        if i == 0: initial_loss = loss
        final_loss = loss
        
        # 3. Backward (Gradiente da Loss)
        # dL/dLogits = P - Y
        d_logits = probs.copy()
        d_logits[rows, targets] -= 1
        d_logits /= len(targets)
        
        grads = model.backward(d_logits, cache)
        
        # 4. Update
        optimizer.step(grads)
        
        if i % 10 == 0:
            print(f"   Epoca {i}: Loss = {loss:.4f}")

    duration = time.time() - start
    print(f"\n   ⏱️ Tempo: {duration:.3f}s")
    print(f"   📉 Loss Inicial: {initial_loss:.4f}")
    print(f"   📉 Loss Final:   {final_loss:.4f}")
    
    if final_loss < initial_loss * 0.5:
        print(Fore.GREEN + "\n✅ SUCESSO: O modelo aprendeu! O gradiente está fluindo.")
    else:
        print(Fore.RED + "\n❌ FALHA: A Loss não caiu o suficiente. Verifique a matemática.")

if __name__ == "__main__":
    train_sanity_check()