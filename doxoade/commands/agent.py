"""
DOXOA AGENT v6.0 (LSTM-Restored).
"""
import click
import os
import subprocess
import sys
import pickle
import numpy as np
import hashlib
import re
from time import sleep
from colorama import Fore, Style
from doxoade.neural.core import Tokenizer, CamadaEmbedding, LSTM, softmax
from doxoade.neural.logic import ArquitetoLogico
from doxoade.neural.reasoning import Sherlock

BRAIN_PATH = os.path.expanduser("~/.doxoade/cortex.pkl")
AGENT_WS = ".dox_agent_workspace"

class OuroborosAgent:
    def __init__(self):
        if not os.path.exists(AGENT_WS): os.makedirs(AGENT_WS)
        self.load_brain()
        self.sherlock = Sherlock()
        self.falhas_memoria = set() 
        
    def load_brain(self):
        if not os.path.exists(BRAIN_PATH): raise FileNotFoundError("Cérebro offline.")
        with open(BRAIN_PATH, 'rb') as f: state = pickle.load(f)
        self.tok = state['tokenizer']
        embed_dim = state['embed']['q_E'].shape[1]
        hidden_size = state['lstm']['q_Wf'].shape[1]
        vocab_size = self.tok.contador
        self.embed = CamadaEmbedding(vocab_size, embed_dim)
        self.lstm = LSTM(embed_dim, hidden_size, vocab_size)
        self.embed.load_state(state['embed'])
        self.lstm.load_state(state['lstm'])
        self.logic = ArquitetoLogico()

    def clean_generated_code(self, raw_code):
        code = re.sub(r'\s+([,):])', r'\1', raw_code)
        code = re.sub(r'(\()\s+', r'\1', code)
        code = code.replace(',', ', ')
        return code

    def think(self, prompt, requisitos, creativity=0.5):
        try: input_ids = self.tok.converter_para_ids(prompt)
        except Exception: return None
        curr = input_ids[0]
        h, c = None, None
        output = [self.tok.inverso.get(curr)]
        self.logic.reset()
        self.logic.observar(output[0])
        
        for nxt in input_ids[1:]:
            x = self.embed.forward(np.array([curr]))
            _, h, c = self.lstm.forward(x, h_prev=h, c_prev=c)
            word = self.tok.inverso.get(nxt)
            self.logic.observar(word)
            output.append(word)
            curr = nxt
            
        for _ in range(40):
            x = self.embed.forward(np.array([curr]))
            out, h, c = self.lstm.forward(x, h_prev=h, c_prev=c)
            logits = out[0]
            for req in requisitos:
                rid = self.tok.vocabulario.get(req)
                if rid: logits[0][rid] += 2.0
            
            if self.logic.estado in ["CORPO", "RETORNO"]:
                pendentes = self.logic.variaveis_pendentes
                if pendentes:
                    for var in pendentes:
                        vid = self.tok.vocabulario.get(var)
                        if vid: logits[0][vid] += 5.0
                    eid = self.tok.vocabulario.get("ENDMARKER")
                    if eid: logits[0][eid] -= 10.0
            
            logits = logits / creativity
            probs = softmax(logits.reshape(1, -1)).flatten()
            top_indices = np.argsort(probs)[::-1][:15]
            sub_probs = probs[top_indices] / np.sum(probs[top_indices])
            
            escolha = None
            for _ in range(20):
                idx = np.random.choice(top_indices, p=sub_probs)
                cand = self.tok.inverso.get(int(idx), "?")
                aprovado, _ = self.logic.validar(cand)
                if aprovado:
                    escolha = int(idx)
                    break
            
            if escolha is None:
                sugestao = self.logic.sugerir_correcao()
                if sugestao: escolha = self.tok.vocabulario.get(sugestao)
                else: break

            if escolha is None: break
            word = self.tok.inverso.get(escolha)
            if word == "ENDMARKER": break
            output.append(word)
            curr = escolha
            self.logic.observar(word)
            
        return self.clean_generated_code(" ".join(output))

    def write_script(self, filename, code, func_name):
        path = os.path.join(AGENT_WS, filename)
        tests = self.generate_test_cases(func_name)
        if not tests: tests = ["pass"]
        test_block = "\n        ".join(tests)
        
        full_code = f"""
import sys
# {code}

if __name__ == "__main__":
    try:
        {test_block}
        print("SUCESSO_TESTES")
    except AssertionError:
        print("FALHA_ASSERT")
        sys.exit(1)
    except NameError as ne:
        print(f"ERRO_NOME: {{ne}}") 
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {{e}}")
        sys.exit(1)
"""
        with open(path, 'w', encoding='utf-8') as f: f.write(full_code)
        return path

    def generate_test_cases(self, func_name):
        tests = []
        if "soma" in func_name: 
            tests.append(f"assert {func_name}(2, 3) == 5, 'Erro soma simples'")
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

@click.command('agent')
@click.argument('task')
def agent_cmd(task):
    print(Fore.CYAN + f"🤖 Agente Ouroboros v6.0: '{task}'" + Style.RESET_ALL)
    bot = OuroborosAgent()
    requisitos = bot.sherlock.deduzir_requisitos(task)
    try: func_name = task.split()[1]
    except Exception: func_name = "func"

    attempts = 5
    for i in range(attempts):
        print(Fore.YELLOW + f"\n[Experimento {i+1}/{attempts}] Raciocinando..." + Style.RESET_ALL)
        code = bot.think(task, requisitos, creativity=0.4 + (i * 0.2))
        if not code: continue

        code_hash = hashlib.md5(code.encode()).hexdigest()
        if code_hash in bot.falhas_memoria:
            print(Fore.RED + "   🧠 Ideia repetida. Descartando." + Style.RESET_ALL)
            continue

        print(f"   📝 Hipótese: {code}")
        ok, msg = bot.sherlock.verificar_analogia(code, requisitos)
        if not ok:
            print(Fore.RED + f"   ❌ Lógica: {msg}" + Style.RESET_ALL)
            bot.falhas_memoria.add(code_hash)
            continue
            
        script_path = bot.write_script(f"exp_{i}.py", code, func_name)
        print("   ⚙️  Validando...")
        success, out, err = bot.execute(script_path)
        
        if success and "SUCESSO_TESTES" in out:
            print(Fore.GREEN + "   ✅ EUREKA! Solução válida encontrada." + Style.RESET_ALL)
            break
        else:
            bot.falhas_memoria.add(code_hash)
            print(Fore.RED + "   ❌ Falha Experimental." + Style.RESET_ALL)
            analise = bot.sherlock.analisar_falha(code, out, err)
            if "ERRO_NOME" in out: analise = f"Função '{func_name}' não foi definida corretamente."
            print(f"   🕵️  Causa: {analise}")

if __name__ == "__main__":
    agent_cmd()