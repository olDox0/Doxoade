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
    """🧠 Motor Neural (Custom Samples)."""
    pass

@brain.command()
@click.option('--epochs', default=200, help='Ciclos de treinamento.')
@click.option('--batch', default=32, help='Tamanho do Virtual Batch.')
@click.option('--samples', default=200, help='Quantidade de dados sintéticos para gerar.')
@click.option('--prune', is_flag=True, help='Ativa a poda neural.')
@click.option('--tbptt', default=50, help='Janela de Truncated BPTT.')
def train(epochs, batch, samples, prune, tbptt):
    """Treina o Córtex com controle de volume de dados."""
    loader = BrainLoader()
    
    print(Fore.YELLOW + "--- FASE 1: Geração de Dados (Ambiente Estéril) ---" + Style.RESET_ALL)
    # Passamos o parametro samples aqui
    data_train = loader.get_training_data(limit=samples)
    
    tok = Tokenizer()
    # Treina o tokenizer com os dados gerados
    all_text = [p[0] + " " + p[1] for p in data_train]
    tok.treinar(all_text)
    
    EMBED_DIM = 32
    HIDDEN_SIZE = 128
    
    embed = CamadaEmbedding(tok.contador, EMBED_DIM)
    lstm = LSTM(EMBED_DIM, HIDDEN_SIZE, tok.contador)
    
    # Carrega estado anterior se vocabulário for compatível
    if os.path.exists(BRAIN_PATH):
        try:
            with open(BRAIN_PATH, 'rb') as f:
                state = pickle.load(f)
                if state['tokenizer'].contador == tok.contador:
                    print(Fore.CYAN + "   [Carregando pesos anteriores...]" + Style.RESET_ALL)
                    embed.load_state(state['embed'])
                    lstm.load_state(state['lstm'])
                else:
                    print(Fore.RED + "   [Vocabulário mudou. Reiniciando.]" + Style.RESET_ALL)
        except: pass

    def train_sequence_truncated(ids, lr, window_size):
        total_loss = 0
        steps = 0
        h = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
        c = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
        
        for i in range(0, len(ids) - 1, window_size):
            chunk_input = ids[i : i + window_size]
            chunk_target = ids[i + 1 : i + window_size + 1]
            if len(chunk_input) == 0: break

            vetores = embed.forward(chunk_input)
            logits, h, c = lstm.forward(vetores, h_prev=h, c_prev=c)
            
            probs = softmax(logits.reshape(len(chunk_input), tok.contador))
            probs = np.clip(probs, 1e-7, 1.0 - 1e-7)
            
            loss = 0
            dY = probs.copy()
            for t, target in enumerate(chunk_target):
                loss += -np.log(probs[t][target])
                dY[t][target] -= 1
            loss /= len(chunk_input)
            total_loss += loss
            steps += 1
            
            dInputs = lstm.accumulate_grad(dY)
            embed.accumulate_grad(dInputs)
            
            lstm.apply_update(lr, batch_size=1)
            embed.apply_update(lr, batch_size=1)
            
        return total_loss / max(steps, 1)

    lr = 0.005
    start_time = time.time()
    
    # Prepara dataset de IDs
    full_dataset = []
    for inp, tgt in data_train:
        full_seq = inp + " " + tgt
        full_dataset.append(tok.converter_para_ids(full_seq))

    print(f"Iniciando treino (Amostras: {len(full_dataset)}, Epochs: {epochs})...")

    for e in range(epochs):
        epoch_loss = 0
        np.random.shuffle(full_dataset)
        
        for seq_ids in full_dataset:
            epoch_loss += train_sequence_truncated(seq_ids, lr, tbptt)
            
        avg_loss = epoch_loss / len(full_dataset)

        if e % 10 == 0:
            elapsed = time.time() - start_time
            msg = f"   Epoca {e}: Perda {avg_loss:.4f} ({elapsed:.1f}s)"
            if prune and e > 20:
                sparsity = lstm.prune(threshold_percentile=5) 
                msg += f" | ✂️ {sparsity:.1f}%"
            print(msg)
            start_time = time.time()

    state_dict = {
        "embed": embed.get_state(),
        "lstm": lstm.get_state(),
        "tokenizer": tok
    }
    
    os.makedirs(os.path.dirname(BRAIN_PATH), exist_ok=True)
    with open(BRAIN_PATH, 'wb') as f:
        pickle.dump(state_dict, f)
        
    size_kb = os.path.getsize(BRAIN_PATH) / 1024
    click.echo(Fore.GREEN + f"💾 Córtex salvo em {BRAIN_PATH} ({size_kb:.1f} KB)" + Style.RESET_ALL)

@brain.command()
@click.argument('prompt')
@click.option('--temp', default=0.7, help='Temperatura (Criatividade).')
def consult(prompt, temp):
    if not os.path.exists(BRAIN_PATH):
        click.echo("❌ Cérebro não encontrado.")
        return
        
    with open(BRAIN_PATH, 'rb') as f:
        state = pickle.load(f)
    
    tok = state["tokenizer"]
    vocab_size = tok.contador
    embed_dim = state['embed']['q_E'].shape[1]
    hidden_size = state['lstm']['q_Wf'].shape[1] // 4 # Ajuste para fused weights
    
    embed = CamadaEmbedding(vocab_size, embed_dim)
    lstm = LSTM(embed_dim, hidden_size, vocab_size)
    
    embed.load_state(state['embed'])
    lstm.load_state(state['lstm'])
    
    arquiteto = ArquitetoLogico()
    
    try:
        input_ids = tok.converter_para_ids(prompt)
    except:
        click.echo("Token desconhecido.")
        return

    curr_id = input_ids[0]
    h, c = None, None
    texto = [tok.inverso.get(curr_id)]
    
    for next_id in input_ids[1:]:
        palavra = tok.inverso.get(next_id)
        arquiteto.observar(palavra)
        x = embed.forward(np.array([curr_id]))
        _, h, c = lstm.forward(x, h_prev=h, c_prev=c)
        curr_id = next_id
        texto.append(palavra)
        
    click.echo(Fore.CYAN + f"Prompt: {' '.join(texto)} " + Fore.GREEN, nl=False)
    
    for _ in range(30):
        x = embed.forward(np.array([curr_id]))
        out, h_next, c_next = lstm.forward(x, h_prev=h, c_prev=c)
        
        logits = out[0] / temp
        probs = softmax(logits.reshape(1, -1)).flatten()
        
        top_indices = np.argsort(probs)[::-1][:10]
        # Normalização segura
        soma = np.sum(probs[top_indices])
        if soma > 0: top_probs = probs[top_indices] / soma
        else: top_probs = np.ones(len(top_indices)) / len(top_indices)
        
        escolha = None
        for _ in range(10): 
            try:
                idx = np.random.choice(top_indices, p=top_probs)
            except: idx = top_indices[0]
            
            cand = tok.inverso.get(int(idx), "?")
            aprovado, _ = arquiteto.validar(cand)
            if aprovado:
                escolha = int(idx)
                break
        
        if escolha is None:
            sug = arquiteto.sugerir_correcao()
            if sug: escolha = tok.vocabulario.get(sug)
            else: escolha = int(top_indices[0])

        if escolha is None: break 
        
        palavra = tok.inverso.get(escolha)
        if palavra == "ENDMARKER":
            click.echo(Fore.YELLOW + " [FIM]" + Style.RESET_ALL)
            break
            
        click.echo(f"{palavra} ", nl=False)
        
        h, c = h_next, c_next
        curr_id = escolha
        arquiteto.observar(palavra)