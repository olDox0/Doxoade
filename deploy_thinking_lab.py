# deploy_thinking_lab.py
import os
import sys
import time
from colorama import init, Fore, Style

init(autoreset=True)

# Força UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

BASE_DIR = os.path.join("doxoade", "thinking")

# --- CONTEÚDO DOS ARQUIVOS ---

CODE_INIT = '"""Pacote Thinking (System 2)."""'

CODE_ASSOCIATOR = r'''
import json
import os
from collections import defaultdict
from ..tools.filesystem import _find_project_root

class Associator:
    def __init__(self):
        root = _find_project_root()
        self.memory_path = os.path.join(root, ".doxoade", "associative_memory.json")
        self.synapses = defaultdict(dict)
        self.load()

    def learn_association(self, source, target, weight=0.1):
        if source == target: return
        s, t = source.lower(), target.lower()
        current = self.synapses[s].get(t, 0.0)
        new_w = min(1.0, current + weight)
        self.synapses[s][t] = new_w
        self.synapses[t][s] = new_w

    def infer_relations(self, concepts, threshold=0.2):
        activated = defaultdict(float)
        for concept in concepts:
            c = concept.lower()
            activated[c] += 1.0
            if c in self.synapses:
                for neighbor, weight in self.synapses[c].items():
                    if weight > threshold:
                        activated[neighbor] += weight
        sorted_mems = sorted(activated.items(), key=lambda x: x[1], reverse=True)
        return [item for item in sorted_mems[:10]]

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump({k: dict(v) for k, v in self.synapses.items()}, f, indent=2)
        except: pass

    def load(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items(): self.synapses[k] = v
            except: pass
'''

CODE_PLANNER = r'''
class ExecutivePlanner:
    def __init__(self):
        self.working_memory = []
        self.current_goal = None

    def set_goal(self, goal):
        self.current_goal = goal
        self.working_memory = []

    def formulate_strategy(self, context_analysis):
        plan = []
        concepts = [c[0] for c in context_analysis]
        
        # Lógica DMFC (Hierárquica)
        if any(w in concepts for w in ['error', 'exception', 'fail', 'crash', 'bug']):
            plan.append("DIAGNOSE_TRACEBACK")
            if any(w in concepts for w in ['import', 'module', 'package']):
                plan.append("CHECK_DEPENDENCIES")
            elif any(w in concepts for w in ['syntax', 'indent']):
                plan.append("FIX_SYNTAX")
            else:
                plan.append("ANALYZE_LOGIC")
                
        elif any(w in concepts for w in ['create', 'new', 'generate', 'scaffold']):
            plan.append("SCAFFOLD_STRUCTURE")
            plan.append("GENERATE_CODE")
            
        elif any(w in concepts for w in ['slow', 'optimize', 'fast']):
            plan.append("RUN_PROFILER")
            
        else:
            plan.append("READ_CONTEXT")
            plan.append("EXECUTE_TASK")
            
        return plan
'''

CODE_CORE = r'''
import re
from .associator import Associator
from .planner import ExecutivePlanner

class ThinkingCore:
    def __init__(self):
        self.associator = Associator()
        self.planner = ExecutivePlanner()

    def process_thought(self, user_input, file_context=None):
        # 1. Atenção (Extração)
        raw_concepts = self._tokenize(user_input)
        if file_context:
            raw_concepts.extend(self._tokenize(file_context)[:10])

        # 2. Associação (Parietal)
        expanded_context = self.associator.infer_relations(raw_concepts)
        
        # 3. Planejamento (Frontal)
        self.planner.set_goal(user_input)
        strategy = self.planner.formulate_strategy(expanded_context)
        
        # 4. Aprendizado (Consolidação)
        u_concepts = list(set(raw_concepts))
        for i in range(len(u_concepts)):
            for j in range(i + 1, len(u_concepts)):
                self.associator.learn_association(u_concepts[i], u_concepts[j])
        self.associator.save()

        return {
            "focus": raw_concepts,
            "associations": [x[0] for x in expanded_context],
            "plan": strategy
        }

    def _tokenize(self, text):
        if not text: return []
        ignore = {'the', 'a', 'is', 'in', 'to', 'for', 'of', 'and', 'with', 'def', 'class'}
        clean = re.sub(r'[^a-zA-Z0-9_]', ' ', text.lower())
        return [w for w in clean.split() if len(w) > 2 and w not in ignore]
'''

def install_files():
    print(Fore.CYAN + "[DEPLOY] Criando estrutura neural 'doxoade/thinking'...")
    os.makedirs(BASE_DIR, exist_ok=True)
    
    files = {
        "__init__.py": CODE_INIT,
        "associator.py": CODE_ASSOCIATOR,
        "planner.py": CODE_PLANNER,
        "core.py": CODE_CORE
    }
    
    for fname, content in files.items():
        path = os.path.join(BASE_DIR, fname)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content.strip())
        print(f"   > Gravado: {fname}")
    print(Fore.GREEN + "[OK] Módulos instalados.\n")

def run_simulation():
    print(Fore.YELLOW + "🧠 [SIMULAÇÃO] Inicializando ThinkingCore (System 2)...")
    
    # Importação dinâmica para garantir que pega os arquivos recém-criados
    try:
        from doxoade.thinking.core import ThinkingCore
        brain = ThinkingCore()
    except ImportError as e:
        print(Fore.RED + f"[ERRO] Falha ao importar ThinkingCore: {e}")
        return

    # CENÁRIO 1: Erro Técnico
    input1 = "Ocorreu um ImportError critico no modulo check"
    print(Fore.WHITE + f"\n🔹 Input 1: '{input1}'")
    thought1 = brain.process_thought(input1)
    
    print(f"   🔎 Foco: {thought1['focus']}")
    print(f"   🕸️  Associações: {thought1['associations']}")
    print(Fore.CYAN + f"   📋 PLANO: {thought1['plan']}")

    # CENÁRIO 2: Solicitação Criativa (Testando o Aprendizado)
    # Como rodamos o Cenario 1, ele deve ter associado 'import' com 'check'
    input2 = "Preciso criar um scaffold novo"
    print(Fore.WHITE + f"\n🔹 Input 2: '{input2}'")
    thought2 = brain.process_thought(input2)
    
    print(f"   🔎 Foco: {thought2['focus']}")
    print(Fore.CYAN + f"   📋 PLANO: {thought2['plan']}")
    
    print(Fore.GREEN + "\n[SUCESSO] O Lobo Frontal está operacional.")

if __name__ == "__main__":
    install_files()
    # Pequena pausa para o sistema de arquivos (Windows as vezes precisa)
    time.sleep(0.5)
    run_simulation()