# doxoade/commands/alfagold.py
import click
import os
import numpy as np
from colorama import Fore, Style
from ..neural.alfagold.model import Alfagold
from ..neural.alfagold.trainer import AlfaTrainer

MODEL_PATH = os.path.expanduser("~/.doxoade/alfagold_v1.pkl")

@click.group()
def alfagold():
    """🌟 Motor Neural Transformer (Next-Gen)."""
    pass

@alfagold.command()
@click.argument('text')
def analyze(text):
    """Analisa a complexidade vetorial de um texto."""
    model = Alfagold()
    if os.path.exists(MODEL_PATH):
        try: model.load(MODEL_PATH)
        except: pass

    print(Fore.CYAN + f"   🧠 Processando: '{text}'")
    ids = model.tokenizer.encode(text)
    print(f"   🔢 Tokens IDs: {ids}")
    logits, _ = model.forward(ids)
    print(Fore.GREEN + "   ✅ Análise concluída.")

@alfagold.command()
def init_model():
    """Inicializa um novo modelo Alfagold limpo."""
    model = Alfagold(vocab_size=2000, d_model=64)
    model.save(MODEL_PATH)
    print(Fore.GREEN + f"🌟 Novo modelo inicializado.")

@alfagold.command()
@click.option('--epochs', default=10)
@click.option('--samples', default=100)
@click.option('--level', default=4)
def train(epochs, samples, level):
    """Treina o Alfagold com dados sintéticos."""
    trainer = AlfaTrainer()
    trainer.train_cycle(epochs=epochs, samples=samples, difficulty=level)

@alfagold.command()
@click.argument('prompt')
@click.option('--length', default=100) # Aumentei um pouco para códigos maiores
@click.option('--temp', default=0.7)
def generate(prompt, length, temp):
    """Gera código usando o modelo Alfagold."""
    model = Alfagold()
    
    if not os.path.exists(MODEL_PATH):
        print(Fore.RED + "❌ Modelo não encontrado."); return

    try:
        model.load(MODEL_PATH)
        print(Fore.GREEN + "   💾 Cérebro carregado.")
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao carregar: {e}"); return

    print(Fore.CYAN + f"   📝 Prompt: '{prompt}'")
    print(Fore.YELLOW + "   🤖 Escrevendo: ", end="", flush=True)
    
    input_ids = model.tokenizer.encode(prompt)
    generated_ids = []
    
    # [FIX] Descobre o ID do token de parada
    end_token_id = model.tokenizer.vocab.get("ENDMARKER", -1)
    
    for _ in range(length):
        current_seq = input_ids + generated_ids
        logits, _ = model.forward(current_seq)
        
        next_token_logits = logits[-1] / temp
        
        # Softmax e Amostragem
        exp_logits = np.exp(next_token_logits - np.max(next_token_logits))
        probs = exp_logits / np.sum(exp_logits)
        next_id = int(np.random.choice(len(probs), p=probs))
        
        # [FIX] Critério de Parada
        if next_id == end_token_id:
            break
            
        generated_ids.append(next_id)
        
        # Feedback visual minimalista (um ponto por token gerado)
        print(".", end="", flush=True)

    print(Fore.GREEN + " [OK]\n")
    
    final_text = model.tokenizer.decode(generated_ids)
    
    print(Style.BRIGHT + "-" * 40)
    # Mostra o prompt + o que foi gerado
    print(Fore.WHITE + prompt + Fore.GREEN + final_text)
    print(Style.BRIGHT + "-" * 40 + Style.RESET_ALL)