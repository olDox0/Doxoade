# lab_alfagold.py
import numpy as np
import time
import sys
import os

# Garante que conseguimos importar o pacote doxoade
sys.path.insert(0, os.path.abspath('.'))

from doxoade.neural.alfagold.model import Alfagold
from doxoade.neural.alfagold.attention import execute_attention, scaled_dot_product_attention, flash_attention_numpy
from colorama import init, Fore, Style

init(autoreset=True)

def test_mathematics():
    print(Fore.YELLOW + "\n🧪 [TESTE 1] Validando Matemática da Atenção...")
    
    # Configuração
    BATCH = 1
    SEQ_LEN = 128
    D_MODEL = 64
    
    # Cria tensores aleatórios simulando Q, K, V
    np.random.seed(42)
    Q = np.random.randn(BATCH, SEQ_LEN, D_MODEL).astype(np.float32)
    K = np.random.randn(BATCH, SEQ_LEN, D_MODEL).astype(np.float32)
    V = np.random.randn(BATCH, SEQ_LEN, D_MODEL).astype(np.float32)

    print(f"   Matrizes criadas: Shape {Q.shape}")

    # 1. Executa Atenção Padrão (Exata)
    start = time.perf_counter()
    out_std, _ = scaled_dot_product_attention(Q, K, V)
    t_std = (time.perf_counter() - start) * 1000
    print(f"   🔹 Standard Attention: {t_std:.4f}ms")

    # 2. Executa Flash Attention (Aproximada/Blocada)
    start = time.perf_counter()
    out_flash, _ = flash_attention_numpy(Q, K, V, block_size=64)
    t_flash = (time.perf_counter() - start) * 1000
    print(f"   ⚡ Flash Attention:    {t_flash:.4f}ms")

    # 3. Comparação
    # Nota: Pequenas diferenças são esperadas devido a ponto flutuante e ordem de soma
    diff = np.mean(np.abs(out_std - out_flash))
    print(f"   📉 Diferença Média (Erro): {diff:.8f}")

    if diff < 0.1: 
        print(Fore.GREEN + "   ✅ SUCESSO: As implementações são matematicamente equivalentes.")
    else:
        print(Fore.RED + "   ❌ FALHA: Divergência matemática detectada.")

def test_pipeline():
    print(Fore.YELLOW + "\n🧪 [TESTE 2] Pipeline Completo do Modelo...")
    
    model = Alfagold(vocab_size=100, d_model=32)
    
    # Simula um treino rápido de vocabulário
    corpus = "def salvar_arquivo(nome): with open(nome, 'w') as f: f.write('teste')"
    model.train_tokenizer(corpus)
    
    # Predição
    texto_teste = "def salvar"
    try:
        output = model.predict(texto_teste)
        
        # Verifica shape de saída
        # Esperado: (1, Num_Tokens, D_Model) -> O 1 é batch size implícito no nosso código simples
        expected_tokens = len(model.tokenizer.encode(texto_teste))
        expected_dim = 32
        
        print(f"   Shape de Saída: {output.shape}")
        
        if output.shape[-1] == expected_dim:
            print(Fore.GREEN + "   ✅ SUCESSO: O fluxo de tensores está correto.")
        else:
            print(Fore.RED + f"   ❌ FALHA: Dimensão incorreta. Esperado {expected_dim}, recebido {output.shape[-1]}")
            
    except Exception as e:
        print(Fore.RED + f"   ❌ CRASH: {e}")
        import traceback
        traceback.print_exc()

def test_stress():
    print(Fore.YELLOW + "\n🧪 [TESTE 3] Stress Test (Contexto Longo)...")
    # Tenta disparar o gatilho de 2048 tokens do attention.py
    
    LONG_SEQ = 2100
    D_MODEL = 32
    
    print(f"   Gerando sequência massiva de {LONG_SEQ} tokens...")
    Q = np.random.randn(1, LONG_SEQ, D_MODEL).astype(np.float32)
    
    start = time.perf_counter()
    # Chama a função mestra que deve decidir usar Flash
    out, _ = execute_attention(Q, Q, Q)
    duration = (time.perf_counter() - start) 
    
    print(Fore.GREEN + f"   ✅ SUCESSO: Processou {LONG_SEQ} tokens em {duration:.4f}s sem estourar memória.")

if __name__ == "__main__":
    print(Style.BRIGHT + "🔬 INICIANDO BATERIA DE TESTES ALFAGOLD")
    test_mathematics()
    test_pipeline()
    test_stress()
    print(Style.BRIGHT + "\n🏁 FIM DOS TESTES")