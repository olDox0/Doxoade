# debug_alfagold.py
import pickle
import os
import sys

# Garante que as classes estejam no path para o pickle carregar
sys.path.insert(0, os.path.abspath('.'))
from doxoade.neural.alfagold.tokenizer import AlfagoldTokenizer

path = os.path.expanduser("~/.doxoade/alfagold_v1.pkl")

if not os.path.exists(path):
    print("❌ Modelo não encontrado.")
    sys.exit(1)

print(f"🔍 Inspecionando Cérebro em: {path}")

try:
    with open(path, 'rb') as f:
        # Carrega o estado do objeto Alfagold
        state = pickle.load(f)

    # O Tokenizer deve estar dentro do estado
    if 'tokenizer' in state:
        tok = state['tokenizer']
        print(f"✅ Tokenizer encontrado. Tipo: {type(tok)}")
        print(f"📊 Tamanho do Vocabulário: {len(tok.vocab)}")
        print(f"📊 Tamanho do Vocabulário Inverso: {len(tok.inverse_vocab)}")
        
        # Teste com os IDs que o modelo gerou no seu log
        ids_suspeitos = [6, 86, 263, 1204]
        print(f"\n🕵️  Decodificando IDs suspeitos: {ids_suspeitos}")
        
        for i in ids_suspeitos:
            raw_token = tok.inverse_vocab.get(i, "NÃO ENCONTRADO")
            decoded = tok.decode([i])
            print(f"   ID {i}: Raw='{raw_token}' (Repr: {repr(raw_token)}) -> Decoded='{decoded}'")

        # Teste reverso
        teste = "def salvar"
        encoded = tok.encode(teste)
        print(f"\n🔄 Teste de Sanidade (Encode/Decode):")
        print(f"   Original: '{teste}'")
        print(f"   IDs: {encoded}")
        print(f"   Decoded: '{tok.decode(encoded)}'")
        
    else:
        print("❌ Chave 'tokenizer' não encontrada no state.")
        print(f"   Chaves disponíveis: {list(state.keys())}")

except Exception as e:
    print(f"❌ Erro ao ler pickle: {e}")