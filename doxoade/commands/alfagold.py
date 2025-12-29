# doxoade/commands/alfagold.py
import click
import os
import numpy as np
from colorama import Fore, Style
from ..neural.alfagold.model import Alfagold
from ..neural.alfagold.trainer import AlfaTrainer
from ..neural.logic import ArquitetoLogico
from ..neural.hrl import HRLAgent

# [NOVO] O Cérebro Unificado
from ..neural.hive import HiveMind

MODEL_PATH = os.path.expanduser("~/.doxoade/alfagold_v1.pkl")


@click.group()
def alfagold():
    """🌟 Motor Neural Transformer (Next-Gen)."""
    pass

# ... (Mantenha os comandos analyze, init_model, train iguais) ...
@alfagold.command()
@click.argument('text')
def analyze(text):
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
    model = Alfagold(vocab_size=2000, d_model=64)
    model.save(MODEL_PATH)
    print(Fore.GREEN + f"🌟 Novo modelo inicializado.")

@alfagold.command()
@click.option('--epochs', default=10)
@click.option('--samples', default=100)
@click.option('--level', default=4)
def train(epochs, samples, level):
    trainer = AlfaTrainer()
    trainer.train_cycle(epochs=epochs, samples=samples, difficulty=level)

@alfagold.command()
@click.argument('prompt')
@click.option('--length', default=100)
@click.option('--temp', default=0.7)
@click.option('--hive', is_flag=True, help="Ativa a Mente de Colmeia (Sistemas Unificados).")
def generate(prompt, length, temp, hive):
    """Gera código usando o modelo Alfagold."""
    model = Alfagold()
    
    if not os.path.exists(MODEL_PATH):
        print(Fore.RED + "❌ Modelo não encontrado."); return

    try:
        model.load(MODEL_PATH)
        print(Fore.GREEN + "   💾 Cérebro carregado.")
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao carregar: {e}"); return

    # Inicializa Componentes
    hrl_agent = HRLAgent(model)
    arquiteto = ArquitetoLogico()
    
    # Inicializa a Mente Unificada
    brain = HiveMind(worker=model, manager=hrl_agent, logic=arquiteto)

    print(Fore.CYAN + f"   📝 Prompt: '{prompt}'")
    if hive: print(Fore.MAGENTA + "   🧬 HIVE MIND: ATIVA (Fusão Neuro-Simbólica)")
    
    print(Fore.YELLOW + "   🤖 Escrevendo: ", end="", flush=True)
    
    input_ids = model.tokenizer.encode(prompt)
    generated_ids = []
    end_token_id = model.tokenizer.vocab.get("ENDMARKER", -1)
    
    # Sincroniza Arquiteto
    for token_id in input_ids:
        token_str = model.tokenizer.decode([token_id]).strip()
        if token_str: arquiteto.observar(token_str)
    
    for _ in range(length):
        current_seq = input_ids + generated_ids
        
        # O HIVE toma a decisão unificada
        if hive:
            next_id = brain.think_and_act(current_seq, temp=temp)
        else:
            # Modo Legado (Só Worker)
            logits, _ = model.forward(current_seq)
            probs = np.exp(logits[-1]) / np.sum(np.exp(logits[-1]))
            next_id = int(np.random.choice(len(probs), p=probs))

        if next_id == end_token_id: break
        generated_ids.append(next_id)
        print(".", end="", flush=True)

    print(Fore.GREEN + " [OK]\n")
    
    final_text = model.tokenizer.decode(generated_ids)
    print(Style.BRIGHT + "-" * 40)
    print(Fore.WHITE + prompt + Fore.GREEN + final_text)
    print(Style.BRIGHT + "-" * 40 + Style.RESET_ALL)