# doxoade/commands/alfagold.py
import click
import os
import sys
import numpy as np
from colorama import Fore, Style

# [FIX] Garante que a raiz do projeto esteja no PATH para importar 'alfagold'
current_dir = os.path.dirname(os.path.abspath(__file__)) # .../doxoade/commands
project_root = os.path.dirname(os.path.dirname(current_dir)) # .../ (Raiz)
if project_root not in sys.path: sys.path.insert(0, project_root)

# [FIX] Imports Absolutos da Nova Arquitetura
try:
    from alfagold.core.transformer import Alfagold
    # from alfagold.training.trainer import AlfaTrainer # (Se existir na nova estrutura)
    from alfagold.experts.refinement_expert import RefinementExpert
    from alfagold.hive.hive_mind import HiveMindMoE
    from alfagold.experts.syntax_expert import SyntaxExpert
    from alfagold.experts.planning_expert import PlanningExpert
except ImportError as e:
    # Fallback ou erro descritivo se a migração estiver incompleta
    print(Fore.RED + f"Erro de Importação Crítico: {e}")
    print(Fore.YELLOW + "Verifique se a pasta 'alfagold' está na raiz e possui __init__.py")
    # Stub para não quebrar a definição do CLI
    Alfagold = None

MODEL_PATH = os.path.expanduser("~/.doxoade/alfagold_v1.pkl")

@click.group()
def alfagold():
    """🌟 Motor Neural Transformer (Next-Gen)."""
    pass

@alfagold.command()
@click.argument('text')
def analyze(text):
    """Analisa a complexidade vetorial de um texto."""
    if not Alfagold: return
    model = Alfagold()
    if os.path.exists(MODEL_PATH):
        try: model.load(MODEL_PATH)
        except: pass

    print(Fore.CYAN + f"   🧠 Processando: '{text}'")
    ids = model.tokenizer.encode(text)
    print(f"   🔢 Tokens IDs: {ids}")
    # Forward no novo modelo retorna 3 valores
    logits, _, _ = model.forward(ids)
    print(Fore.GREEN + "   ✅ Análise concluída.")

@alfagold.command()
def init_model():
    """Inicializa um novo modelo Alfagold limpo."""
    if not Alfagold: return
    model = Alfagold(vocab_size=2000, d_model=64)
    model.save(MODEL_PATH)
    print(Fore.GREEN + f"🌟 Novo modelo inicializado.")

@alfagold.command()
@click.option('--epochs', default=10)
@click.option('--samples', default=100)
@click.option('--level', default=4)
def train(epochs, samples, level):
    """Treina o Alfagold (Wrapper para o script de treino)."""
    # Como o treino agora é complexo (MTL), chamamos o script dedicado
    from alfagold.training.train_mtl import train_mtl
    train_mtl()

@alfagold.command()
@click.argument('prompt')
@click.option('--length', default=100)
@click.option('--temp', default=0.7)
@click.option('--hive', is_flag=True, help="Ativa a Mente de Colmeia (MoE).")
def generate(prompt, length, temp, hive):
    """Gera código usando o modelo Alfagold."""
    if not Alfagold: return
    
    model = Alfagold()
    
    if not os.path.exists(MODEL_PATH):
        # Tenta carregar o NPZ (Novo formato)
        if not os.path.exists(MODEL_PATH.replace('.pkl', '.npz')):
            print(Fore.RED + "❌ Modelo não encontrado."); return

    try:
        model.load(MODEL_PATH)
        print(Fore.GREEN + "   💾 Cérebro carregado.")
    except Exception as e:
        print(Fore.RED + f"   ❌ Erro ao carregar: {e}"); return

    # Inicializa Cerebelo (Sempre ativo para limpeza)
    cerebelo = RefinementExpert()

    # Inicializa MoE se solicitado
    hive_mind = HiveMindMoE() if hive else None

    print(Fore.CYAN + f"   📝 Prompt: '{prompt}'")
    if hive: print(Fore.MAGENTA + "   🧬 HIVE MIND (MoE): ATIVA")
    
    print(Fore.YELLOW + "   🤖 Escrevendo: ", end="", flush=True)
    
    # Preparação
    # Usa o HiveMind para gerar a sequência completa se ativo
    if hive:
        # O HiveMindMoE já tem seu próprio loop e print de pontos
        # Mas para manter consistência com o Cerebelo aqui fora, 
        # vamos deixar o HiveMind gerar tudo e pegamos o resultado.
        
        # Nota: O método run_sequence do HiveMind já imprime. 
        # Vamos capturar o retorno para passar no Cerebelo.
        print("") # Quebra linha
        raw_text = hive_mind.run_sequence(prompt, length=length)
        # O run_sequence retorna o texto completo
        full_text = raw_text
        
    else:
        # Modo Legado (Apenas Modelo Base)
        input_ids = model.tokenizer.encode(prompt)
        generated_ids = []
        end_token_id = model.tokenizer.vocab.get("ENDMARKER", -1)
        
        for _ in range(length):
            current_seq = input_ids + generated_ids
            logits, _, _ = model.forward(current_seq)
            next_token_logits = logits[-1]
            
            scaled_logits = np.clip(next_token_logits / temp, -50, 50)
            exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
            probs = exp_logits / np.sum(exp_logits)
            
            next_id = int(np.random.choice(len(probs), p=probs))
            
            if next_id == end_token_id: break
            generated_ids.append(next_id)
            print(".", end="", flush=True)

        print(Fore.GREEN + " [OK]\n")
        raw_gen = model.tokenizer.decode(generated_ids)
        full_text = prompt + raw_gen

    # [FIX] APLICA O CEREBELO (Refinamento Pós-Processamento)
    # Se usou Hive, o texto já vem meio limpo, mas o Cerebelo v3 garante a indentação
    print(Fore.CYAN + "   🔧 Cerebelo: Refinando e Dedup...")
    refined_text = cerebelo.process(full_text)
    
    print(Style.BRIGHT + "-" * 40)
    print(Fore.WHITE + refined_text)
    print(Style.BRIGHT + "-" * 40 + Style.RESET_ALL)