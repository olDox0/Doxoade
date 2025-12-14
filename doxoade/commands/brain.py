# doxoade/commands/brain.py
import click
import pickle
import os
import time
import numpy as np
from colorama import Fore, Style
from doxoade.neural.core import Tokenizer, CamadaEmbedding, LSTM, softmax
from doxoade.neural.adapter import BrainLoader
from doxoade.neural.logic import ArquitetoLogico

BRAIN_PATH = os.path.expanduser("~/.doxoade/cortex.pkl")

@click.group()
def brain():
    """🧠 Motor Neural (Neuro-Suite)."""
    pass

@brain.command()
@click.option('--epochs', default=500, help='Ciclos de treinamento.')
def train(epochs):
    """Treina o córtex com Curriculo Learning (Python -> Linter)."""
    loader = BrainLoader()
    
    # FASE 1: DADOS SINTÉTICOS (Aprender Python)
    print(Fore.YELLOW + "--- FASE 1: Alfabetização em Python ---" + Style.RESET_ALL)
    data_python = loader._generate_synthetic_batch(100) # Gera 100 exemplos puros
    
    # FASE 2: DADOS REAIS (Aprender Doxoade)
    print(Fore.YELLOW + "--- FASE 2: Especialização em Engenharia ---" + Style.RESET_ALL)
    data_linter = loader.get_training_data() # Pega do banco + sintéticos misturados
    
    # Tokenizer precisa ver tudo
    tok = Tokenizer()
    all_text = [p[0] + " " + p[1] for p in data_python + data_linter]
    tok.treinar(all_text)
    
    # Arquitetura
    EMBED_DIM = 32
    HIDDEN_SIZE = 128
    embed = CamadaEmbedding(tok.contador, EMBED_DIM)
    lstm = LSTM(input_size=EMBED_DIM, hidden_size=HIDDEN_SIZE, output_size=tok.contador)
    
    # Função auxiliar de treino
    def run_epoch(dataset, lr):
        total_loss = 0
        for inp_text, target_text in dataset:
            # Adiciona EOS para ensinar parada
            full_seq = inp_text + " " + target_text
            #if "<EOS>" not in full_seq: full_seq += " <EOS>"
            if "ENDMARKER" not in full_seq: full_seq += " ENDMARKER"
            ids = tok.converter_para_ids(full_seq)
            input_ids = ids[:-1]
            target_ids = ids[1:]
            
            vetores = embed.forward(input_ids)
            logits, _, _ = lstm.forward(vetores)
            probs = softmax(logits.reshape(len(input_ids), tok.contador))
            
            loss = 0
            dY = probs.copy()
            for t, target in enumerate(target_ids):
                loss += -np.log(probs[t][target] + 1e-8)
                dY[t][target] -= 1
            loss /= len(input_ids)
            total_loss += loss
            
            dInputs = lstm.backward(dY, lr=lr)
            embed.backward(dInputs, lr=lr)
        return total_loss / len(dataset)

    # LOOP DE TREINO (LR Schedule)
    lr = 0.5
    
    print("Treinando Base (Sintaxe)...")
    for e in range(int(epochs / 2)):
        loss = run_epoch(data_python, lr)
        if e % 50 == 0: print(f"   Epoca {e}: {loss:.4f}")
    
    print("\nTreinando Especialização (Regras)...")
    lr = 0.1 # Diminui LR para refinar sem esquecer o Python
    for e in range(int(epochs / 2)):
        loss = run_epoch(data_linter, lr)
        if e % 50 == 0: print(f"   Epoca {e}: {loss:.4f}")

    # Salvar
    modelo = {"embed": embed, "lstm": lstm, "tokenizer": tok}
    os.makedirs(os.path.dirname(BRAIN_PATH), exist_ok=True)
    with open(BRAIN_PATH, 'wb') as f:
        pickle.dump(modelo, f)
    click.echo(Fore.GREEN + f"💾 Córtex salvo em {BRAIN_PATH}" + Style.RESET_ALL)

@brain.command()
@click.argument('prompt')
def consult(prompt):
    """Gera sugestões de código baseadas no contexto."""
    if not os.path.exists(BRAIN_PATH):
        click.echo("❌ Cérebro não encontrado. Rode 'doxoade brain train'.")
        return
        
    with open(BRAIN_PATH, 'rb') as f:
        modelo = pickle.load(f)
    
    embed, lstm, tok = modelo["embed"], modelo["lstm"], modelo["tokenizer"]
    arquiteto = ArquitetoLogico()
    
    try:
        input_ids = tok.converter_para_ids(prompt)
    except:
        click.echo("Token desconhecido.")
        return

    curr_id = input_ids[0]
    h, c = None, None
    texto = [tok.inverso.get(curr_id)]
    
    # Aquecimento (Pre-fill)
    for next_id in input_ids[1:]:
        palavra = tok.inverso.get(next_id)
        arquiteto.observar(palavra)
        x = embed.forward(np.array([curr_id]))
        _, h, c = lstm.forward(x, h_prev=h, c_prev=c)
        curr_id = next_id
        texto.append(palavra)
        
    click.echo(Fore.CYAN + f"Prompt: {' '.join(texto)} " + Fore.GREEN, nl=False)
    
    # Geração Híbrida (Neuro-Simbólica)
    for _ in range(15):
        x = embed.forward(np.array([curr_id]))
        out, h_next, c_next = lstm.forward(x, h_prev=h, c_prev=c)
        probs = out[0].flatten()
        
        top_indices = np.argsort(probs)[::-1][:5]
        escolha = None
        
        for idx in top_indices:
            cand = tok.inverso.get(int(idx), "?")
            aprovado, _ = arquiteto.validar(cand)
            if aprovado:
                escolha = int(idx)
                break
        
        if escolha is None: break 
        
        palavra = tok.inverso.get(escolha)
        if palavra == "ENDMARKER":
            click.echo(Fore.YELLOW + " [FIM]" + Style.RESET_ALL)
            break
            
        click.echo(f"{palavra} ", nl=False)
        
        h, c = h_next, c_next
        curr_id = escolha
        arquiteto.observar(palavra)
        
        if arquiteto.estado == "RETORNO" and len(texto) > 10 and palavra.isalnum():
            break

    click.echo(Style.RESET_ALL)
