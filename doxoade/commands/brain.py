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
    """🧠 Motor Neural (Fused Gates + TBPTT)."""
    pass

@brain.command()
@click.option('--epochs', default=200, help='Ciclos de treinamento.')
@click.option('--batch', default=32, help='Tamanho do Virtual Batch.')
@click.option('--prune', is_flag=True, help='Ativa a poda neural.')
@click.option('--tbptt', default=50, help='Janela de Truncated BPTT.')
def train(epochs, batch, prune, tbptt):
    """Treina com Fusão de Matrizes e Backprop Truncado."""
    loader = BrainLoader()
    
    print(Fore.YELLOW + "--- FASE 1: Alfabetização (Sintaxe) ---" + Style.RESET_ALL)
    data_python = loader._generate_synthetic_batch(100)
    print(Fore.YELLOW + "--- FASE 2: Especialização (Regras) ---" + Style.RESET_ALL)
    data_linter = loader.get_training_data()
    
    tok = Tokenizer()
    all_text = [p[0] + " " + p[1] for p in data_python + data_linter]
    tok.treinar(all_text)
    
    EMBED_DIM = 32
    HIDDEN_SIZE = 128
    
    # Casting explícito para garantir compatibilidade com novos args
    embed = CamadaEmbedding(tok.contador, EMBED_DIM)
    lstm = LSTM(EMBED_DIM, HIDDEN_SIZE, tok.contador)
    
    # Tenta carregar anterior se existir (apenas se vocabulário bater)
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
        except Exception: pass

    def train_sequence_truncated(ids, lr, window_size):
        """
        Treina uma sequência longa em pedaços pequenos.
        """
        total_loss = 0
        steps = 0
        
        # Estado inicial zerado
        h = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
        c = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
        
        # Loop pelos chunks
        for i in range(0, len(ids) - 1, window_size):
            chunk_input = ids[i : i + window_size]
            chunk_target = ids[i + 1 : i + window_size + 1]
            
            if len(chunk_input) == 0: break

            # 1. Forward (passando estado anterior)
            vetores = embed.forward(chunk_input)
            
            # IMPORTANTE: h e c são atualizados e passados para o próximo chunk
            # Mas no backward, o gradiente MORRE aqui (detach implícito do NumPy)
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
            
            # 2. Backward Truncado
            dInputs = lstm.accumulate_grad(dY)
            embed.accumulate_grad(dInputs)
            
            # 3. Update Imediato (Online Learning)
            lstm.apply_update(lr, batch_size=1)
            embed.apply_update(lr, batch_size=1)
            
        return total_loss / max(steps, 1)

    lr = 0.005
    start_time = time.time()
    
    # Dataset unificado de IDs
    full_dataset = []
    for inp, tgt in data_python + data_linter:
        full_seq = inp + " " + tgt
        if "ENDMARKER" not in full_seq: full_seq += " ENDMARKER"
        full_dataset.append(tok.converter_para_ids(full_seq))

    print(f"Iniciando treino (TBPTT: {tbptt}, Amostras: {len(full_dataset)})...")

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
    click.echo(Fore.GREEN + f"💾 Córtex v8 salvo em {BRAIN_PATH} ({size_kb:.1f} KB)" + Style.RESET_ALL)

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
    # Recupera Hidden Size da matriz Wf (Input+Hidden, Hidden)
    # Wf.shape[1] é Hidden. Wf.shape[0] é Input+Hidden.
    hidden_size = state['lstm']['q_W'].shape[1] // 4 # W agora é (I+H, 4H)
    
    embed = CamadaEmbedding(vocab_size, embed_dim)
    lstm = LSTM(embed_dim, hidden_size, vocab_size)
    
    embed.load_state(state['embed'])
    lstm.load_state(state['lstm'])
    
    arquiteto = ArquitetoLogico()
    
    try:
        input_ids = tok.converter_para_ids(prompt)
    except Exception:
        click.echo("Token desconhecido.")
        return

    curr_id = input_ids[0]
    h, c = None, None
    texto = [tok.inverso.get(curr_id)]
    
    # Pre-fill
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
        out, h, c = lstm.forward(x, h_prev=h, c_prev=c)
        
        logits = out[0] / temp
        probs = softmax(logits.reshape(1, -1)).flatten()
        
        top_indices = np.argsort(probs)[::-1][:10]
        top_probs = probs[top_indices] / np.sum(probs[top_indices])
        
        escolha = None
        for _ in range(10): 
            try:
                idx = np.random.choice(top_indices, p=top_probs)
            except Exception: idx = top_indices[0]
            
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
        
        h, c = h, c
        curr_id = escolha
        arquiteto.observar(palavra)