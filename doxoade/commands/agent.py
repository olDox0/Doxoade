# doxoade/commands/agent.py
import click
import sys
import os
import sqlite3
import subprocess
import numpy as np
import hashlib
import pickle
import re
from colorama import Fore, Style
from datetime import datetime, timezone

# Imports do Núcleo Neural
from doxoade.neural.core import Tokenizer, LSTM, CamadaEmbedding, load_json, save_json, softmax
from doxoade.neural.logic import ArquitetoLogico
from doxoade.neural.reasoning import Sherlock
from doxoade.neural.rl_engine import QLearner
from doxoade.neural.critic import Critic
from doxoade.neural.memory import VectorDB

# [NOVO] Integração com o Córtex Frontal (System 2)
from doxoade.thinking.core import ThinkingCore

from doxoade.database import get_db_connection

class Librarian:
    def __init__(self):
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()

    def lembrar(self, task):
        # Busca solução exata baseada em hash da tarefa
        task_hash = hashlib.md5(task.encode()).hexdigest()
        try:
            self.cursor.execute("SELECT solution FROM memory WHERE task_hash = ?", (task_hash,))
            row = self.cursor.fetchone()
            if row: return row[0]
        except Exception: 
            return None
        return None

    def memorizar(self, task, code):
        task_hash = hashlib.md5(task.encode()).hexdigest()
        try:
            self.cursor.execute("INSERT OR REPLACE INTO memory (task_hash, task_desc, solution) VALUES (?, ?, ?)", 
                                (task_hash, task, code))
            self.conn.commit()
            return True
        except Exception: 
            return False

class OuroborosAgent:
    def __init__(self):
        self.brain_path = os.path.expanduser("~/.doxoade/cortex.pkl")
        self.tok = Tokenizer()
        self.embed = None
        self.lstm = None
        
        # Subsistemas Lógicos
        self.logic = ArquitetoLogico()
        self.sherlock = Sherlock()
        self.rl = QLearner()
        self.critic = Critic()
        self.vectordb = VectorDB()
        
        # [NOVO] System 2 (Planejamento e Associação)
        try:
            self.thinking = ThinkingCore()
            self.has_thinking = True
        except Exception as e:
            print(Fore.RED + f"[AVISO] ThinkingCore indisponível: {e}")
            self.has_thinking = False

        self.load_brain()

    def load_brain(self):
        if os.path.exists(self.brain_path):
            try:
                with open(self.brain_path, 'rb') as f:
                    dados = pickle.load(f)
                    self.tok = dados['tokenizer']
                    self.embed = dados['embed']
                    self.lstm = dados['lstm']
            except Exception:
                pass # Cérebro limpo

        if self.embed is None:
            # Inicialização a frio (Cold Start)
            self.embed = CamadaEmbedding(1000, 64)
            self.lstm = LSTM(64, 128, 1000)

    def absorber_vocabulario(self, prompt):
        # O tokenizer aprende dinamicamente com o prompt
        self.tok.treinar([prompt])
        vocab_size = self.tok.contador
        if vocab_size > self.lstm.O:
            print(Fore.YELLOW + f"   🌱 Neuroplasticidade: Expandindo vocabulário ({self.lstm.O} -> {vocab_size})...")
            self.lstm.expand_vocab(vocab_size)

    def vectorize(self, text):
        # Converte texto para vetor semântico (usando a LSTM como encoder)
        try:
            ids = self.tok.converter_para_ids(text)
            x = self.embed.forward(ids)
            _, h, c = self.lstm.forward(x.reshape(1,-1))
            return h.flatten()[-1] # Último estado oculto
        except Exception:
            return np.zeros(self.lstm.H)

    def consolidar_aprendizado(self, prompt, codigo_correto):
        # Online Learning: Treina a rede imediatamente com o sucesso
        full_text = prompt + " " + codigo_correto + " ENDMARKER"
        try: 
            ids = self.tok.converter_para_ids(full_text)
        except Exception: 
            return
            
        input_ids = ids[:-1]
        target_ids = ids[1:]
        lr = 0.05
        
        # Forward
        x = self.embed.forward(input_ids)
        y_pred, _, _ = self.lstm.forward(x.reshape(-1, 1, 64))
        
        # Backward (Cross-Entropy simplificado)
        dY = softmax(y_pred)
        for t, target in enumerate(target_ids):
            dY[t, 0, target] -= 1
            
        dInputs = self.lstm.accumulate_grad(dY)
        self.embed.accumulate_grad(dInputs.reshape(-1, 64))
        
        # Update
        self.lstm.apply_update(lr, 1)
        self.embed.apply_update(lr, 1)
        
        # Salvar estado
        state = {
            'tokenizer': self.tok,
            'embed': self.embed,
            'lstm': self.lstm
        }
        with open(self.brain_path, 'wb') as f:
            pickle.dump(state, f)
            
        # Memorização Vetorial
        vec = self.vectorize(prompt)
        self.vectordb.add(vec, payload=codigo_correto)

    def clean_generated_code(self, raw_code):
        # Remove artefatos de tokens
        code = raw_code.replace("ENDMARKER", "").replace("<PAD>", "").replace("<UNK>", "")
        return code.strip()

    def think(self, prompt, intent="generic", priors=None, creativity=0.5):
        # [NOVO] System 2 Pre-Processing
        context_boost = []
        if self.has_thinking:
            print(Fore.CYAN + "🧠 [SYSTEM 2] Planejando...")
            thought_process = self.thinking.process_thought(prompt)
            
            # Adiciona associações ao vocabulário da rede
            associacoes = thought_process['associations']
            if associacoes:
                print(Fore.CYAN + f"   🕸️  Associações: {', '.join(associacoes[:5])}")
                context_boost = associacoes
                # Treina o tokenizer com os conceitos novos para que ele saiba usá-los
                self.absorber_vocabulario(" ".join(associacoes))

        self.absorber_vocabulario(prompt)
        
        try: 
            input_ids = self.tok.converter_para_ids(prompt)
        except Exception: 
            return None
            
        curr = input_ids[0]
        h, c = None, None
        output = []
        
        self.logic.reset()
        # Se Sherlock deu priors, usamos para validar (ex: aridade mínima)
        min_args = 2 if "soma" in prompt or "add" in prompt else 0
        self.logic.set_constraints(min_args=min_args)

        MAX_TOKENS = 50
        
        for _ in range(MAX_TOKENS):
            # Embed & Forward
            x = self.embed.forward(np.array([curr]))
            logits, h, c = self.lstm.forward(x.reshape(1, 1, -1), h_prev=h, c_prev=c)
            logits = logits[0, 0, :]
            
            # Aplica Prioris do Sherlock (Bayes)
            if priors:
                for token, prob in priors.items():
                    idx = self.tok.vocabulario.get(token)
                    if idx: logits[idx] += np.log(prob + 1e-9)

            # [NOVO] Aplica Boost do System 2 (Contexto)
            for ctx_word in context_boost:
                idx = self.tok.vocabulario.get(ctx_word)
                if idx: logits[idx] += 0.5 # Leve viés para palavras do contexto

            # Aplica RL Boost (Q-Learning)
            prev_token_str = self.tok.inverso.get(str(curr), "<UNK>")
            for cand_idx in range(len(logits)):
                cand_str = self.tok.inverso.get(str(cand_idx), "<UNK>")
                logits[cand_idx] += self.rl.get_boost(prev_token_str, cand_str)

            # Amostragem (Temperature Sampling)
            probs = softmax(logits.reshape(1, -1) / creativity).flatten()
            
            # Filtro do Arquiteto Lógico (DFA)
            top_indices = np.argsort(probs)[::-1]
            idx = top_indices[0]
            
            for candidate_idx in top_indices:
                token_str = self.tok.inverso.get(str(candidate_idx), "?")
                valido, motivo = self.logic.validar(token_str)
                if valido:
                    idx = candidate_idx
                    # Reforço positivo no RL para transição válida
                    self.rl.update(prev_token_str, token_str, 0.1) 
                    break
                else:
                    # Punição no RL para transição inválida
                    self.rl.update(prev_token_str, token_str, -0.1)

            # Auto-Correção
            token_escolhido = self.tok.inverso.get(str(idx), "?")
            sugestao = self.logic.sugerir_correcao()
            if sugestao:
                token_escolhido = sugestao
                idx = self.tok.vocabulario.get(sugestao, idx)

            self.logic.observar(token_escolhido)
            output.append(token_escolhido)
            curr = idx
            
            if token_escolhido == "ENDMARKER": break
            
        return " ".join(output)

    def write_script(self, filename, code, func_name):
        # [Aegis] Garante encoding utf-8
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("import sys\nimport os\n") # Imports básicos padrão
            
            # [Inteligência] Adiciona imports detectados no contexto
            if "math" in code: f.write("import math\n")
            if "random" in code: f.write("import random\n")
            if "json" in code: f.write("import json\n")
            
            f.write("\n")
            f.write(code.replace("ENDMARKER", ""))
            f.write("\n\n")
            
            # Gera Teste Unitário Dinâmico (Self-Test)
            test_cases = self.generate_test_cases(func_name)
            f.write(f"if __name__ == '__main__':\n")
            f.write(f"    try:\n")
            for case in test_cases:
                f.write(f"        {case}\n")
            f.write(f"        print('SUCESSO_TESTES')\n")
            f.write(f"    except Exception as e:\n") # [Aegis] Catch Exception, not bare except
            f.write(f"        print(f'FALHA_ASSERT: {{e}}')\n")
            f.write(f"        sys.exit(1)\n")

    def generate_test_cases(self, func_name):
        # Sherlock poderia gerar isso, mas por enquanto hardcoded para segurança
        if func_name in ["soma", "add"]: return [f"assert {func_name}(1, 1) == 2", f"assert {func_name}(10, 5) == 15"]
        if func_name in ["sub", "diff"]: return [f"assert {func_name}(10, 5) == 5"]
        if func_name in ["mult", "prod"]: return [f"assert {func_name}(3, 3) == 9"]
        return [f"print('Teste genérico para {func_name}')"]

    def execute(self, filepath):
        # [Aegis] Executa em subprocesso seguro, sem shell=True
        python_exe = sys.executable
        result = subprocess.run(
            [python_exe, filepath], 
            capture_output=True, 
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode, result.stdout, result.stderr

    def diagnostico_her(self, codigo, func_name_original):
        # Heurística de Reparo Emergencial (HER) v2
        # Prioridade 1: Estrutura (Definição)
        if "def " not in codigo: 
            return f"def {func_name_original}(a, b): return a + b"
        
        # Prioridade 2: Lógica (Retorno)
        if "return" not in codigo: 
            return codigo + "\n    return None"
            
        return codigo

# --- COMANDO CLI ---

@click.command('agent')
@click.argument('task')
def agent_cmd(task):
    """
    Agente Autônomo Ouroboros (System 1 + System 2).
    Ciclo: Pensar -> Gerar -> Testar -> Aprender.
    """
    print(Fore.CYAN + f"🤖 Ouroboros: Analisando tarefa '{task}'...")
    
    lib = Librarian()
    memoria = lib.lembrar(task)
    if memoria:
        print(Fore.GREEN + "   💡 Solução lembrada da memória de longo prazo!")
        print(Fore.WHITE + memoria)
        return

    bot = OuroborosAgent()
    
    # 1. Inferência Bayesiana (Sherlock) - System 1.5
    priors, intent = bot.sherlock.get_priors(task)
    print(Fore.YELLOW + f"   🕵️  Sherlock: Intenção provável = '{intent}'")
    
    try: 
        func_name = task.split()[1] # Ex: "criar soma" -> soma
    except Exception: 
        func_name = "func_temp"

    attempts = 5
    best_code = None
    
    for i in range(attempts):
        print(Fore.BLUE + f"\n[Tentativa {i+1}/{attempts}]")
        
        # 2. Geração Neural (Córtex + Arquiteto + Thinking)
        creativity = 1.0 if i == 0 else 0.8 # Mais criativo no início, mais conservador depois
        raw_code = bot.think(task, intent, priors, creativity)
        
        if not raw_code:
            print(Fore.RED + "   [FALHA] Córtex não gerou saída.")
            continue
            
        clean_code = bot.clean_generated_code(raw_code)
        
        # Fallback se a rede gerar lixo
        if len(clean_code) < 10: 
            clean_code = bot.diagnostico_her(clean_code, func_name)
            
        print(Fore.WHITE + f"   Código Gerado: {clean_code}")
        
        # 3. Validação Empírica (Sandbox)
        temp_file = "temp_agent_task.py"
        bot.write_script(temp_file, clean_code, func_name)
        
        ret, out, err = bot.execute(temp_file)
        
        # 4. Julgamento (Critic)
        veredito, culpado, tipo_erro = bot.critic.julgar_execucao(out, err, clean_code)
        
        if veredito == "SUCESSO":
            print(Fore.GREEN + "   ✅ SUCESSO! O código passou nos testes.")
            best_code = clean_code
            
            # 5. Consolidação (Learning)
            print(Fore.MAGENTA + "   🧠 Consolidando aprendizado (Neuroplasticidade)...")
            bot.consolidar_aprendizado(task, clean_code)
            
            # Atualiza crenças do Sherlock
            bot.sherlock.atualizar_crenca(intent, "+", True) # Simplificado
            
            # Salva no DB
            lib.memorizar(task, clean_code)
            
            if os.path.exists(temp_file): os.remove(temp_file)
            break
        
        else:
            print(Fore.RED + f"   ❌ FALHA ({veredito}). Culpado: {culpado} ({tipo_erro})")
            # Punição Bayesiana
            bot.sherlock.atualizar_crenca(intent, "+", False)
    
    if not best_code:
        print(Fore.RED + "\n[FALHA] O agente não conseguiu resolver a tarefa após várias tentativas.")