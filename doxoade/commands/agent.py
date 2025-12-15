"""
DOXOADE AGENT v9.2 (Final Polish).
Correção de argumentos na consolidação de memória.
"""
import click
import os
import subprocess
import sys
import pickle
import numpy as np
import hashlib
import re
from colorama import Fore, Style
from doxoade.neural.core import Tokenizer, CamadaEmbedding, LSTM, softmax
from doxoade.neural.logic import ArquitetoLogico
from doxoade.neural.reasoning import Sherlock
from doxoade.neural.critic import Critic

BRAIN_PATH = os.path.expanduser("~/.doxoade/cortex.pkl")
AGENT_WS = ".dox_agent_workspace"

class OuroborosAgent:
    def __init__(self):
        if not os.path.exists(AGENT_WS): os.makedirs(AGENT_WS)
        self.load_brain()
        self.sherlock = Sherlock()
        self.critic = Critic()
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

    def consolidar_aprendizado(self, prompt, codigo_correto):
        print(Fore.MAGENTA + "   🧠 Consolidando memória neural (Neuroplasticidade)..." + Style.RESET_ALL)
        
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
            
            # CORREÇÃO AQUI: batch_size=1
            self.lstm.apply_update(lr, batch_size=1)
            self.embed.apply_update(lr, batch_size=1)

        state = {
            "embed": self.embed.get_state(),
            "lstm": self.lstm.get_state(),
            "tokenizer": self.tok
        }
        with open(BRAIN_PATH, 'wb') as f: pickle.dump(state, f)
        print(Fore.MAGENTA + "   💾 Conhecimento salvo permanentemente." + Style.RESET_ALL)

    def clean_generated_code(self, raw_code):
        code = re.sub(r'\s+([,):])', r'\1', raw_code)
        code = re.sub(r'(\()\s+', r'\1', code)
        code = code.replace(',', ', ')
        return code

    def think(self, prompt, intent, priors, creativity=0.5):
        try: input_ids = self.tok.converter_para_ids(prompt)
        except: return None
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
            
            for op, prob in priors.items():
                oid = self.tok.vocabulario.get(op)
                if oid: logits[0][oid] += np.log(prob + 1e-5) * 2.0 + 5.0
            
            if self.logic.estado in ["CORPO", "RETORNO"]:
                pendentes = self.logic.variaveis_pendentes
                if pendentes:
                    for var in pendentes:
                        vid = self.tok.vocabulario.get(var)
                        if vid: logits[0][vid] += 5.0
                    eid = self.tok.vocabulario.get("ENDMARKER")
                    if eid: logits[0][eid] -= 10.0
            
            if len(output) > 1:
                last = self.tok.vocabulario.get(output[-1])
                if last: logits[0][last] -= 3.0

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
        # Indentação correta para dentro do try
        bloco = "\n        ".join(tests)
        
        # Limpa o código para garantir indentação correta
        code_lines = [line.strip() for line in code.splitlines() if line.strip()]
        code_clean = "\n".join(code_lines)

        full_code = f"""
import sys

# Codigo Gerado:
{code_clean}

if __name__ == "__main__":
    try:
        {bloco}
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
            tests.append(f"assert {func_name}(2, 3) == 5")
            tests.append(f"assert {func_name}(10, 5) == 15")
        elif "sub" in func_name: tests.append(f"assert {func_name}(5, 2) == 3")
        elif "mult" in func_name: tests.append(f"assert {func_name}(3, 3) == 9")
        elif "maior" in func_name: tests.append(f"assert {func_name}(5, 2) == 5")
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
    print(Fore.CYAN + f"🤖 Agente Ouroboros v9.2: '{task}'" + Style.RESET_ALL)
    bot = OuroborosAgent()
    priors, intent = bot.sherlock.get_priors(task)
    try: func_name = task.split()[1]
    except: func_name = "func"

    attempts = 5
    for i in range(attempts):
        print(Fore.YELLOW + f"\n[Experimento {i+1}/{attempts}] Gerando..." + Style.RESET_ALL)
        
        code = bot.think(task, intent, priors, creativity=0.4 + (i * 0.2))
        if not code: continue

        code_hash = hashlib.md5(code.encode()).hexdigest()
        if code_hash in bot.falhas_memoria:
            print(Fore.RED + "   🧠 Memória: Falha repetida. Ignorando." + Style.RESET_ALL)
            continue

        print(f"   📝 Hipótese: {code}")
        
        # Validação Sherlock
        ok, msg = bot.sherlock.verificar_analogia(code, []) 
        if not ok:
            print(Fore.RED + f"   ❌ Sherlock: {msg}" + Style.RESET_ALL)
            continue

        script_path = bot.write_script(f"exp_{i}.py", code, func_name)
        print("   ⚙️  Executando...")
        success, out, err = bot.execute(script_path)
        
        veredito, culpado, tipo_erro = bot.critic.julgar_execucao(out, err, code)
        
        if veredito == "SUCESSO":
            print(Fore.GREEN + "   ✅ EUREKA! O código funciona!" + Style.RESET_ALL)
            ops = [op for op in ["+", "-", "*", "/"] if f" {op} " in code]
            for op in ops: bot.sherlock.atualizar_crenca(intent, op, sucesso=True)
            
            code_limpo = code.replace(task, "").strip()
            bot.consolidar_aprendizado(task, code_limpo)
            break
            
        elif veredito == "INOCENTE":
            print(Fore.BLUE + f"   🛡️  Erro de Ambiente ({tipo_erro})." + Style.RESET_ALL)
            print(f"   Log: {out} {err}")

        else:
            print(Fore.RED + f"   ❌ Falha Lógica ({tipo_erro})." + Style.RESET_ALL)
            bot.falhas_memoria.add(code_hash)
            ops = [op for op in ["+", "-", "*", "/"] if f" {op} " in code]
            for op in ops: 
                bot.sherlock.atualizar_crenca(intent, op, sucesso=False)
                print(f"   📉 Sherlock: Confiança em '{op}' diminuída.")

if __name__ == "__main__":
    agent_cmd()