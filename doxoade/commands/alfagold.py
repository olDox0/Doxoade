# doxoade/commands/alfagold.py
import click
import os
import numpy as np
from colorama import Fore, Style
from ..neural.alfagold.model import Alfagold
from ..neural.alfagold.trainer import AlfaTrainer

# Importa os dois sistemas de controle
from ..neural.logic import ArquitetoLogico
from ..neural.hrl import HRLAgent

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
@click.option('--length', default=100)
@click.option('--temp', default=0.7)
@click.option('--strict', is_flag=True, help="Ativa o Arquiteto Lógico (Regras Rígidas).")
@click.option('--hrl', is_flag=True, help="Ativa o Agente Hierárquico (Rede Neural de Decisão).")
def generate(prompt, length, temp, strict, hrl):
    """Gera código usando o modelo Alfagold."""
    model = Alfagold()
    
    if not os.path.exists(MODEL_PATH):
        print(Fore.RED + "❌ Modelo não encontrado."); return

    try:
        model.load(MODEL_PATH)
        print(Fore.GREEN + "   💾 Cérebro carregado.")
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao carregar: {e}"); return

    # Inicializa Agentes
    hrl_agent = HRLAgent(model) if hrl else None
    arquiteto = ArquitetoLogico() if strict else None

    print(Fore.CYAN + f"   📝 Prompt: '{prompt}'")
    
    if hrl: print(Fore.MAGENTA + "   👑 HRL Manager: ATIVO (Estratégia Neural)")
    elif strict: print(Fore.BLUE + "   🛡️  Arquiteto Lógico: ATIVO (Regras Simbólicas)")
    
    print(Fore.YELLOW + "   🤖 Escrevendo: ", end="", flush=True)
    
    input_ids = model.tokenizer.encode(prompt)
    generated_ids = []
    end_token_id = model.tokenizer.vocab.get("ENDMARKER", -1)
    
    # Alimenta o Arquiteto com o prompt inicial se necessário
    if strict:
        for token_id in input_ids:
            token_str = model.tokenizer.decode([token_id]).strip()
            if token_str: arquiteto.observar(token_str)
    
    for _ in range(length):
        current_seq = input_ids + generated_ids
        
        # 1. Obtenção de Logits (Probabilidades)
        if hrl:
            # HRL modifica os logits baseado na intenção do Manager
            logits, current_option = hrl_agent.step(current_seq)
            next_token_logits = logits # O step já retorna o último
        else:
            # Modo Padrão
            logits, _ = model.forward(current_seq)
            next_token_logits = logits[-1]
        
        # 2. Amostragem
        scaled_logits = next_token_logits / temp
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        # 3. Seleção do Token
        next_id = None
        
        # Se STRICT estiver ativo (e HRL não, para evitar conflito de chefes)
        if strict and not hrl:
            # Tenta pegar os melhores candidatos e validar
            top_indices = np.argsort(probs)[::-1][:10]
            top_probs = probs[top_indices] / np.sum(probs[top_indices])
            
            for _ in range(5):
                cand_idx = int(np.random.choice(top_indices, p=top_probs))
                cand_str = model.tokenizer.decode([cand_idx]).strip()
                if not cand_str: 
                    next_id = cand_idx; break
                valido, _ = arquiteto.validar(cand_str)
                if valido:
                    next_id = cand_idx
                    arquiteto.observar(cand_str)
                    break
            
            if next_id is None:
                sug = arquiteto.sugerir_correcao()
                if sug:
                    sug_ids = model.tokenizer.encode(sug)
                    if sug_ids: next_id = sug_ids[0]; arquiteto.observar(sug)

        # Fallback ou Modo HRL/Normal
        if next_id is None:
            next_id = int(np.random.choice(len(probs), p=probs))

        if next_id == end_token_id: break
        generated_ids.append(next_id)
        print(".", end="", flush=True)

    print(Fore.GREEN + " [OK]\n")
    
    final_text = model.tokenizer.decode(generated_ids)
    
    print(Style.BRIGHT + "-" * 40)
    print(Fore.WHITE + prompt + Fore.GREEN + final_text)
    print(Style.BRIGHT + "-" * 40 + Style.RESET_ALL)