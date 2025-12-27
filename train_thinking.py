# train_thinking.py
import os
import sys
import time
from colorama import init, Fore, Style
from doxoade.thinking.core import ThinkingCore

init(autoreset=True)

def train_brain():
    print(Fore.YELLOW + "🧠 [GENESIS] Iniciando leitura dinâmica da documentação...")
    
    # Instancia o cérebro
    try:
        brain = ThinkingCore()
    except Exception as e:
        print(Fore.RED + f"[ERRO] Não foi possível iniciar o ThinkingCore: {e}")
        return

    docs_path = os.path.join("doxoade", "docs")
    files_processed = 0
    synapses_fired = 0
    start_time = time.time()

    # Percorre recursivamente a pasta docs
    for root, _, filenames in os.walk(docs_path):
        for filename in filenames:
            if filename.endswith(('.md', '.json', '.txt')):
                filepath = os.path.join(root, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Usa o tokenizador do próprio cérebro para extrair conceitos
                    concepts = brain._tokenize(content)
                    
                    if not concepts:
                        continue

                    # Aprendizado por Janela Deslizante (Sliding Window)
                    # Conecta cada conceito com os 5 próximos.
                    # Isso cria contexto: "LSTM" aparece perto de "Ouroboros" -> Conecta.
                    WINDOW_SIZE = 5
                    for i in range(len(concepts) - 1):
                        current_word = concepts[i]
                        # Olha para frente
                        window = concepts[i+1 : i + WINDOW_SIZE + 1]
                        
                        for neighbor in window:
                            # Peso baixo (0.05) pois é uma leitura passiva
                            brain.associator.learn_association(current_word, neighbor, weight=0.05)
                            synapses_fired += 1
                    
                    files_processed += 1
                    print(Fore.CYAN + f"   > Lido: {filename} ({len(concepts)} conceitos extraídos)")
                    
                except Exception as e:
                    print(Fore.RED + f"   [FALHA] {filename}: {e}")

    # Salva a memória de longo prazo
    brain.associator.save()
    
    duration = time.time() - start_time
    print(Fore.GREEN + "\n" + "="*50)
    print(f"📚 LEITURA CONCLUÍDA em {duration:.2f}s")
    print(f"📄 Documentos: {files_processed}")
    print(f"🔗 Sinapses Reforçadas: {synapses_fired}")
    print("="*50)

    # Teste Rápido de Associação
    print(Fore.YELLOW + "\n[TESTE DE COMPREENSÃO]")
    for termo in ['lstm', 'maestro', 'aegis']:
        assocs = brain.associator.infer_relations([termo])
        top = [x[0] for x in assocs[:5]]
        print(f"   Termo '{termo}' lembra: {top}")

if __name__ == "__main__":
    train_brain()