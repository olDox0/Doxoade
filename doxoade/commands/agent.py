"""
DOXOADE AGENT v16.2 (Stable).
Correção final de variáveis e escopo de execução.
"""
import click
import os
import subprocess
import sys
import pickle
import sqlite3
import numpy as np
import hashlib
import re
from datetime import datetime, timezone
from colorama import Fore, Style
from doxoade.neural.core import load_json, save_json, Tokenizer, CamadaEmbedding, LSTM, softmax
from doxoade.neural.logic import ArquitetoLogico
from doxoade.neural.reasoning import Sherlock
from doxoade.neural.critic import Critic
from doxoade.database import get_db_connection
from doxoade.neural.memory import VectorDB
from doxoade.neural.rl_engine import QLearner

BRAIN_PATH = os.path.expanduser("~/.doxoade/cortex.json")
AGENT_WS = ".dox_agent_workspace"

class Librarian:
    def __init__(self):
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()
    def lembrar(self, task):
        try:
            self.cursor.execute("SELECT stable_content FROM solutions WHERE message LIKE ? LIMIT 1", (f"%{task}%",))
            row = self.cursor.fetchone()
            if row: return row[0]
        except: pass
        return None
    def memorizar(self, task, code):
        if "<UNK>" in code or "ENDMARKER" in code or code.strip().endswith(":"): return False
        try:
            h = hashlib.sha256(task.encode()).hexdigest()
            self.cursor.execute("INSERT OR REPLACE INTO solutions (finding_hash, stable_content, commit_hash, project_path, timestamp, message, file_path, error_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (h, code, "AGENT", "neural_memory", datetime.now(timezone.utc).isoformat(), task, "agent_memory", 0))
            self.conn.commit()
            return True
        except: return False

class OuroborosAgent:
    def __init__(self):
        if not os.path.exists(AGENT_WS): os.makedirs(AGENT_WS)
        self.load_brain()
        self.sherlock = Sherlock()
        self.critic = Critic()
        self.librarian = Librarian()
        self.memory = VectorDB()
        self.rl = QLearner()
        self.falhas_memoria = set() 
        
    def load_brain(self):
        if not os.path.exists(BRAIN_PATH): raise FileNotFoundError("Cérebro offline.")
        state = load_json(BRAIN_PATH)
        self.tok = Tokenizer.from_dict(state['tokenizer'])
        embed_dim = len(state['embed']['E'][0][0])
        hidden_size = len(state['lstm']['Wf'][0][0])
        vocab_size = self.tok.contador
        self.embed = CamadaEmbedding(vocab_size, embed_dim)
        self.lstm = LSTM(embed_dim, hidden_size, vocab_size)
        self.embed.load_state_dict(state['embed'])
        self.lstm.load_state_dict(state['lstm'])
        self.logic = ArquitetoLogico()

    def absorber_vocabulario(self, prompt):
        tokens = self.tok._quebrar(prompt)
        novos = [t for t in tokens if t not in self.tok.vocabulario]
        if novos:
            print(Fore.CYAN + f"   🌱 Absorvendo novos conceitos: {novos}" + Style.RESET_ALL)
            for t in novos: self.tok.adicionar_token(t)
            new_size = self.tok.contador
            self.embed.expand(new_size)
            self.lstm.expand_vocab(new_size)
            state = {"embed": self.embed.get_state_dict(), "lstm": self.lstm.get_state_dict(), "tokenizer": self.tok.to_dict()}
            save_json(state, BRAIN_PATH)

    def vectorize(self, text):
        try:
            ids = self.tok.converter_para_ids(text)
            curr = ids[0]; h, c = None, None
            x = self.embed.forward(np.array([curr]))
            _, h, c = self.lstm.forward(x.reshape(1,-1), h_prev=h, c_prev=c)
            for next_id in ids[1:]:
                x = self.embed.forward(np.array([next_id]))
                _, h, c = self.lstm.forward(x.reshape(1,-1), h_prev=h, c_prev=c)
            return h.flatten()
        except: return None

    def consolidar_aprendizado(self, prompt, codigo_correto):
        if "<UNK>" in codigo_correto or "ENDMARKER" in codigo_correto or codigo_correto.strip().endswith(":"): return
        print(Fore.MAGENTA + "   🧠 Refinando intuição (Treino Online)..." + Style.RESET_ALL)
        vec = self.vectorize(prompt)
        if vec is not None: self.memory.add(vec, codigo_correto)
        
        full_text = prompt + " " + codigo_correto + " ENDMARKER"
        try: ids = self.tok.converter_para_ids(full_text)
        except: return 
        input_ids = ids[:-1]; target_ids = ids[1:]
        lr = 0.05 
        for _ in range(5):
            vetores = self.embed.forward(input_ids)
            logits, _, _ = self.lstm.forward(vetores)
            probs = softmax(logits.reshape(len(input_ids), self.tok.contador))
            dY = probs.copy()
            for t, target in enumerate(target_ids): dY[t][target] -= 1
            dInputs = self.lstm.accumulate_grad(dY)
            self.embed.accumulate_grad(dInputs)
            self.lstm.apply_update(lr, batch_size=1)
            self.embed.apply_update(lr, batch_size=1)
        state = {"embed": self.embed.get_state_dict(), "lstm": self.lstm.get_state_dict(), "tokenizer": self.tok.to_dict()}
        save_json(state, BRAIN_PATH) 
        tokens = full_text.split()
        for i in range(len(tokens)-1): self.rl.update(tokens[i], tokens[i+1], reward=2.0)
        self.rl.save()

    def clean_generated_code(self, raw_code):
        code = re.sub(r'\s+([,):])', r'\1', raw_code)
        code = re.sub(r'(\()\s+', r'\1', code)
        code = code.replace(',', ', ')
        return code

    def think(self, prompt, intent, priors, creativity=0.5):
        self.absorber_vocabulario(prompt)
        try: input_ids = self.tok.converter_para_ids(prompt)
        except: return None
        curr = input_ids[0]; h, c = None, None
        output = [self.tok.inverso.get(str(curr))]
        
        # CONFIGURAÇÃO DE REGRAS DINÂMICAS
        min_args = 0
        if intent in ["soma", "sub", "mult", "div", "adição", "adicionar", "total", "calcular"]:
             min_args = 2
             
        self.logic.reset()
        self.logic.set_constraints(min_args=min_args) 
        self.logic.observar(output[0])
        
        for nxt in input_ids[1:]:
            x = self.embed.forward(np.array([curr]))
            _, h, c = self.lstm.forward(x.reshape(1,-1), h_prev=h, c_prev=c)
            word = self.tok.inverso.get(str(nxt))
            self.logic.observar(word); output.append(word); curr = nxt
            
        for _ in range(40):
            x = self.embed.forward(np.array([curr]))
            out, h, c = self.lstm.forward(x.reshape(1,-1), h_prev=h, c_prev=c)
            logits = out.flatten()
            for op, prob in priors.items():
                oid = self.tok.vocabulario.get(op)
                if oid: logits[oid] += np.log(prob + 1e-5) * 2.0 + 5.0
            if self.logic.estado in ["CORPO", "RETORNO"]:
                pendentes = self.logic.variaveis_pendentes
                if pendentes:
                    for var in pendentes:
                        vid = self.tok.vocabulario.get(var)
                        if vid: logits[vid] += 5.0
                    eid = self.tok.vocabulario.get("ENDMARKER")
                    if eid: logits[eid] -= 10.0
            if len(output) > 1:
                last = self.tok.vocabulario.get(output[-1])
                if last: logits[last] -= 3.0
                for token_id in range(self.tok.contador):
                    token_str = self.tok.inverso.get(str(token_id))
                    q_val = self.rl.get_q(output[-1], token_str)
                    logits[token_id] += q_val * 2.0
            logits = logits / creativity; probs = softmax(logits.reshape(1, -1)).flatten()
            top_indices = np.argsort(probs)[::-1][:15]; sub_probs = probs[top_indices] / np.sum(probs[top_indices])
            escolha = None
            for _ in range(20):
                try: idx = np.random.choice(top_indices, p=sub_probs)
                except: idx = top_indices[0]
                cand = self.tok.inverso.get(str(idx), "?")
                aprovado, _ = self.logic.validar(cand)
                if aprovado: escolha = int(idx); break
            
            # --- FIX: NOME DA VARIÁVEL CORRIGIDO ---
            if escolha is None:
                sugestao = self.logic.sugerir_correcao()
                if sugestao: 
                    escolha = self.tok.vocabulario.get(sugestao)
                else: break
            # ---------------------------------------

            if escolha is None: break
            word = self.tok.inverso.get(str(escolha))
            if word == "ENDMARKER": break
            output.append(word); curr = escolha; self.logic.observar(word)
        return self.clean_generated_code(" ".join(output))

    def write_script(self, filename, code, func_name):
        path = os.path.join(AGENT_WS, filename)
        tests = self.generate_test_cases(func_name)
        if not tests: tests = ["pass"]
        bloco = "\n        ".join(tests)
        
        # Código no escopo global
        full_code = f"""
import sys

# === CÓDIGO DA IA ===
{code}
# ====================

if __name__ == "__main__":
    try:
        # Verifica no escopo global
        if '{func_name}' not in globals():
            print("ERRO_NOME: Função '{func_name}' não encontrada no escopo global.")
            sys.exit(1)
        
        # Smoke Test
        try:
             # Executa a função para ver se crasha ou pede args
             func = globals()['{func_name}']
             func(2,3)
        except TypeError as te:
             print(f"ERRO_ARGS: {{te}}")
             sys.exit(1)
        except Exception: pass

        {bloco}
        print("SUCESSO_TESTES")
    except AssertionError:
        print("FALHA_ASSERT")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {{e}}")
        sys.exit(1)
"""
        with open(path, 'w', encoding='utf-8') as f: f.write(full_code)
        return path

    def generate_test_cases(self, func_name):
        tests = []
        if any(x in func_name for x in ["soma", "adição", "add", "total", "calcular"]): 
            tests.append(f"assert {func_name}(2, 3) == 5")
            tests.append(f"assert {func_name}(10, 5) == 15")
        elif "maior" in func_name:
            tests.append(f"assert {func_name}(5, 2) == 5")
            tests.append(f"assert {func_name}(1, 10) == 10")
        return tests
    
    def execute(self, filepath):
        python_exe = sys.executable
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        try:
            res = subprocess.run([python_exe, filepath], capture_output=True, text=True, encoding='utf-8', timeout=2, env=env)
            return res.returncode == 0, res.stdout, res.stderr
        except subprocess.TimeoutExpired: return False, "", "Timeout"
    def diagnostico_her(self, codigo, func_name_original): pass

@click.command('agent')
@click.argument('task')
def agent_cmd(task):
    print(Fore.CYAN + f"🤖 Agente Ouroboros v16.2 (Stable): '{task}'" + Style.RESET_ALL)
    bot = OuroborosAgent()
    memoria = bot.librarian.lembrar(task)
    # 0. MEMÓRIA
    task_vec = bot.vectorize(task)
    if task_vec is not None:
        memoria = bot.memory.search(task_vec)
        if memoria:
            # FIX: Reconstrói a assinatura se estiver incompleta
            if not memoria.strip().startswith("def "):
                 # Tenta extrair o nome da task (ex: "def calcular_total")
                 # Assume que task já é "def nome"
                 memoria = f"{task} {memoria}"
            
            print(Fore.GREEN + f"   ✅ Já sei fazer isso! (Recuperado do VectorDB)" + Style.RESET_ALL)
            print(f"   📝 Código: {memoria}")
            return
    priors, intent = bot.sherlock.get_priors(task)
    try: func_name = task.split()[1]
    except: func_name = "func"
    attempts = 5
    for i in range(attempts):
        print(Fore.YELLOW + f"\n[Experimento {i+1}/{attempts}] Gerando..." + Style.RESET_ALL)
        code = bot.think(task, intent, priors, creativity=0.4 + (i * 0.2))
        if not code: continue
        if "<UNK>" in code:
             print(Fore.RED + "   ❌ Código sujo (<UNK>). Descartando." + Style.RESET_ALL)
             continue
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        if code_hash in bot.falhas_memoria:
            print(Fore.RED + "   🧠 Memória Curta: Falha repetida." + Style.RESET_ALL)
            continue
        print(f"   📝 Hipótese: {code}")
        ok, msg = bot.sherlock.verificar_analogia(code, []) 
        if not ok:
            print(Fore.RED + f"   ❌ Sherlock: {msg}" + Style.RESET_ALL)
            bot.falhas_memoria.add(code_hash)
            continue
        script_path = bot.write_script(f"exp_{i}.py", code, func_name)
        print("   ⚙️  Validando...")
        success, out, err = bot.execute(script_path)
        veredito, culpado, tipo_erro = bot.critic.julgar_execucao(out, err, code)
        if "ERRO_RETORNO" in out: veredito="CULPADO"; tipo_erro="Função Vazia"
        if "ERRO_ARGS" in out: veredito="CULPADO"; tipo_erro="Argumentos Incorretos"
        if "ERRO_NOME" in out: veredito="CULPADO"; tipo_erro="Nome Incorreto"

        if veredito == "SUCESSO":
            print(Fore.GREEN + "   ✅ EUREKA! Solução válida." + Style.RESET_ALL)
            ops = [op for op in ["+", "-", "*", "/"] if f" {op} " in code]
            for op in ops: bot.sherlock.atualizar_crenca(intent, op, sucesso=True)
            code_limpo = code.replace(task, "").strip()
            bot.librarian.memorizar(task, code_limpo)
            bot.consolidar_aprendizado(task, code_limpo)
            break
        elif veredito == "INOCENTE":
            print(Fore.BLUE + f"   🛡️  Erro de Ambiente ({tipo_erro})." + Style.RESET_ALL)
        else:
            print(Fore.RED + f"   ❌ Falha Lógica ({tipo_erro})." + Style.RESET_ALL)
            if out.strip() or err.strip():
                print(Fore.WHITE + f"   🐛 DUMP: {out.strip()} {err.strip()}")
            bot.falhas_memoria.add(code_hash)
            ops = [op for op in ["+", "-", "*", "/"] if f" {op} " in code]
            for op in ops: bot.sherlock.atualizar_crenca(intent, op, sucesso=False)

if __name__ == "__main__":
    agent_cmd()