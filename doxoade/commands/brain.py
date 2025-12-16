# doxoade/commands/brain.py
"""
DOXONET BRAIN v13.2 (Curriculum Fix).
Correção de variáveis de fase e fluxo de aprendizado.
"""
import click
import pickle
import os
import time
import numpy as np
from colorama import Fore, Style
from doxoade.neural.core import Tokenizer, CamadaEmbedding, LSTM, softmax, save_json, load_json, dequantize
from doxoade.neural.adapter import BrainLoader
from doxoade.neural.logic import ArquitetoLogico
from doxoade.neural.profiler import NeuralProfiler

BRAIN_PATH = os.path.expanduser("~/.doxoade/cortex.json")

@click.group()
def brain():
    """🧠 Motor Neural (Curriculum Learning)."""
    pass

@brain.command()
@click.option('--epochs', default=300, help='Ciclos totais.')
@click.option('--batch', default=32)
@click.option('--samples', default=500)
@click.option('--prune', is_flag=True)
@click.option('--tbptt', default=50)
@click.option('--profile', is_flag=True)
def train(epochs, batch, samples, prune, tbptt, profile):
    
    with NeuralProfiler(enabled=profile):
        loader = BrainLoader()
        tok = Tokenizer()
        
        if os.path.exists(BRAIN_PATH):
            try:
                state = load_json(BRAIN_PATH)
                if 'tokenizer' in state:
                    tok = Tokenizer.from_dict(state['tokenizer'])
            except: pass
        
        # Pré-treino do Tokenizer
        print(Fore.YELLOW + "--- Preparando Vocabulário Global ---" + Style.RESET_ALL)
        sample_level_3 = loader.get_training_data(limit=100, difficulty=3)
        all_text = [p[0] + " " + p[1] for p in sample_level_3]
        tok.treinar(all_text)
        
        EMBED_DIM = 32
        HIDDEN_SIZE = 128
        embed = CamadaEmbedding(tok.contador, EMBED_DIM)
        
        if not os.path.exists(BRAIN_PATH):
            embed.init_symbolic(tok)

        lstm = LSTM(EMBED_DIM, HIDDEN_SIZE, tok.contador)
        
        if os.path.exists(BRAIN_PATH):
             try:
                state = load_json(BRAIN_PATH)
                embed.load_state_dict(state['embed'])
                lstm.load_state_dict(state['lstm'])
                print(Fore.GREEN + "   💉 Córtex carregado." + Style.RESET_ALL)
             except Exception: pass

        def train_sequence_smart(ids, lr, window_size):
            total_loss = 0; steps = 0
            h = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
            c = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
            for i in range(0, len(ids) - 1, window_size):
                chunk_in = ids[i:i+window_size]
                chunk_tgt = ids[i+1:i+window_size+1]
                if len(chunk_in)==0: break
                vecs = embed.forward(chunk_in)
                logits, h, c = lstm.forward(vecs, h_prev=h, c_prev=c)
                probs = softmax(logits.reshape(len(chunk_in), tok.contador))
                probs = np.clip(probs, 1e-7, 1.0-1e-7)
                dY = probs.copy()
                loss = 0
                for t, target in enumerate(chunk_tgt):
                    loss -= np.log(probs[t][target])
                    dY[t][target] -= 1
                loss /= len(chunk_in)
                total_loss += loss; steps += 1
                dIn = lstm.accumulate_grad(dY)
                embed.accumulate_grad(dIn)
                lstm.apply_update(lr, batch_size=1)
                embed.apply_update(lr, batch_size=1)
            return total_loss / max(steps, 1)

        lr = 0.01
        start_time = time.time()
        
        # --- CURRICULUM LOOP (Restaurado) ---
        phase1_end = int(epochs * 0.2) 
        phase2_end = int(epochs * 0.6) 
        
        current_difficulty = 0
        dataset = [] 

        for e in range(epochs):
            new_difficulty = 1
            if e > phase1_end: new_difficulty = 2
            if e > phase2_end: 
                new_difficulty = 3
                if e == phase2_end + 1: lr = 0.001
            
            if new_difficulty != current_difficulty:
                current_difficulty = new_difficulty
                print(Fore.MAGENTA + f"\n📚 --- INICIANDO FASE {current_difficulty} ---" + Style.RESET_ALL)
                raw_data = loader.get_training_data(limit=samples, difficulty=current_difficulty)
                dataset = []
                for inp, tgt in raw_data:
                    seq = inp + " " + tgt
                    dataset.append(tok.converter_para_ids(seq))
            
            np.random.shuffle(dataset)
            epoch_loss = 0
            for seq_ids in dataset:
                epoch_loss += train_sequence_smart(seq_ids, lr, tbptt)
            
            avg_loss = epoch_loss / len(dataset) if len(dataset) > 0 else 0
            
            if e % 10 == 0:
                elapsed = time.time() - start_time
                msg = f"   Epoca {e} (Fase {current_difficulty}): Perda {avg_loss:.4f} ({elapsed:.1f}s)"
                if prune and e > 20:
                     msg += f" | ✂️ {lstm.prune(5):.1f}%"
                print(msg)
                start_time = time.time()

        state = {
            "embed": embed.get_state_dict(),
            "lstm": lstm.get_state_dict(),
            "tokenizer": tok.to_dict()
        }
        save_json(state, BRAIN_PATH)
        click.echo(Fore.GREEN + f"💾 Córtex treinado salvo." + Style.RESET_ALL)

# ... (função consult mantida igual) ...
@brain.command()
@click.argument('prompt')
@click.option('--temp', default=0.7)
def consult(prompt, temp):
    if not os.path.exists(BRAIN_PATH):
        click.echo("❌ Cérebro não encontrado.")
        return
    state = load_json(BRAIN_PATH)
    tok = Tokenizer.from_dict(state['tokenizer'])
    vocab_size = tok.contador
    embed_dim = len(state['embed']['E'][0][0]) 
    hidden_size = len(state['lstm']['Wf'][0][0])
    embed = CamadaEmbedding(vocab_size, embed_dim)
    lstm = LSTM(embed_dim, hidden_size, vocab_size)
    embed.load_state_dict(state['embed'])
    lstm.load_state_dict(state['lstm'])
    arquiteto = ArquitetoLogico()
    try: input_ids = tok.converter_para_ids(prompt)
    except Exception: return
    curr = input_ids[0]; h, c = None, None
    texto = [tok.inverso.get(str(curr))]
    for next_id in input_ids[1:]:
        palavra = tok.inverso.get(str(next_id))
        arquiteto.observar(palavra)
        x = embed.forward(np.array([curr]))
        x_in = x.reshape(1, -1)
        _, h, c = lstm.forward(x_in, h_prev=h, c_prev=c)
        curr = next_id
        texto.append(palavra)
    click.echo(Fore.CYAN + f"Prompt: {' '.join(texto)} " + Fore.GREEN, nl=False)
    for _ in range(30):
        x = embed.forward(np.array([curr]))
        x_in = x.reshape(1, -1)
        out, h, c = lstm.forward(x_in, h_prev=h, c_prev=c)
        logits = out.flatten()
        logits = logits / temp
        probs = softmax(logits.reshape(1, -1)).flatten()
        top_indices = np.argsort(probs)[::-1][:10]
        soma = np.sum(probs[top_indices])
        if soma > 0: top_probs = probs[top_indices] / soma
        else: top_probs = np.ones(len(top_indices)) / len(top_indices)
        escolha = None
        for _ in range(10): 
            try: idx = np.random.choice(top_indices, p=top_probs)
            except Exception: idx = top_indices[0]
            cand = tok.inverso.get(str(idx), "?")
            aprovado, _ = arquiteto.validar(cand)
            if aprovado: escolha = int(idx); break
        if escolha is None:
            sug = arquiteto.sugerir_correcao()
            if sug: escolha = tok.vocabulario.get(sug)
            else: escolha = int(top_indices[0])
        if escolha is None: break 
        palavra = tok.inverso.get(str(escolha))
        if palavra == "ENDMARKER":
            click.echo(Fore.YELLOW + " [FIM]" + Style.RESET_ALL)
            break
        click.echo(f"{palavra} ", nl=False)
        h, c = h, c
        curr = escolha
        arquiteto.observar(palavra)

if __name__ == "__main__":
    pass