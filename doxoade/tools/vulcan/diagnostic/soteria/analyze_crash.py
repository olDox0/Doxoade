# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/analyze_crash.py
"""
Córtex Analítico Lazarus v77.2 - O Mapa da Verdade.
Arquitetura: Multi-Language Dispatcher c/ Isolamento de Assinaturas.
"""
import re
import hashlib
import datetime
import sys
from pathlib import Path
from typing import Dict, Any, List

from doxoade.tools.telemetry_tools.logger import chief_heartbeat
from .crash_signatures import WIN_SIGNALS, PYTHON_EXCEPTIONS, NATIVE_LOGIC_PATTERNS

class CrashProcessor:
    def __init__(self, project_root: str):
        self.root = project_root

    def process(self, raw_text: str, exit_code: int = None) -> Dict[str, Any]:
        d = self._init_dossier(raw_text)
        
        # 1. Filtro de Aborto: Se for SystemExit, não gera diagnóstico
        if "SystemExit" in raw_text or (exit_code == 0):
#        if "SystemExit:" in raw_text or "SystemExit" in raw_text:
            d['technical_error'] = "NORMAL_EXIT"
            return d

        # 2. Roteamento de Diagnóstico
        if "@SOTERIA_BEGIN@" in raw_text or "@NEXUS_BEGIN@" in raw_text:
            self._parse_native(d, raw_text, exit_code)
        elif "Traceback" in raw_text:
            self._parse_python(d, raw_text)
            
        return d

    def _parse_native(self, d: dict, raw: str, exit_code: int):
        match = re.search(r"@(SOTERIA|NEXUS)_BEGIN@(.*?)@(SOTERIA|NEXUS)_END@", raw, re.DOTALL)
        content = match.group(2) if match else raw
        tags = dict(re.findall(r"TAG_(\w+):\s*(.*)", content))
        
        d['technical_error'] = "NATIVE_FAULT"
        d['soteria'] = {k.replace("REG_",""): v for k,v in tags.items() if k.startswith("REG_") or k in ["RIP", "RSP"]}
        d['inventory_raw'] = re.findall(r"TAG_ARENA_OBJ:\s*(.*)", raw)
        d['chain'] = re.findall(r"TAG_FRAME: \d+ \| (.*?) \| (.*)", raw)
        
        loc = tags.get('RASTRO_LOC', "")
        if not loc and d['chain']:
            # Se o rastro explodiu, pegamos o local do último frame válido (topo da pilha)
            loc = d['chain'][0][1] # Pega o "arquivo.c:linha" do frame 0
            
        if loc and ":" in loc:
            f, l = loc.rsplit(':', 1)
            d['file'], d['line'] = self._find_source(f), (int(l) if l.isdigit() else 0)


        # Oráculo Nativo
        motivo = tags.get('MOTIVO', '').upper()
        for entry in NATIVE_LOGIC_PATTERNS:
            if entry[0] in motivo:
                d['technical_error'], d['explanation'] = entry[1], entry[2]
        
        if exit_code in WIN_SIGNALS:
            d['technical_error'], d['explanation'] = WIN_SIGNALS[exit_code]

    def _parse_python(self, d: dict, raw: str):
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines: return
        
        last_line = lines[-1]
        # Remove wrappers do Aegis para o laudo ficar limpo
        clean_msg = re.sub(r'.*?Aegis Sandbox Blocked:\s*', '', last_line).strip()
        
        # Identifica Erro Humano
        from .crash_signatures import PYTHON_EXCEPTIONS
        exc_type = clean_msg.split(":")[0].strip()
        
        if exc_type in PYTHON_EXCEPTIONS:
            d['technical_error'], d['explanation'] = PYTHON_EXCEPTIONS[exc_type]
            d['explanation'] += f" ({clean_msg})"
        else:
            d['technical_error'], d['explanation'] = exc_type, clean_msg

        # Triangulação: Escavação de Pilha
        py_frames = re.findall(r'File "(.+?)", line (\d+), in (.+)', raw)
        if py_frames:
            # Poda de infraestrutura: ignora o que não é código do projeto
            infra = ['aegis_utils.py', 'aegis_core.py', 'run.py', 'rescue.py', 'lazarus_hook.py']
            
            target = None
            for frame in reversed(py_frames):
                if not any(noise in frame[0] for noise in infra):
                    target = frame
                    break
            
            target = target or py_frames[-1]
            d['file'] = self._find_source(target[0])
            d['line'] = int(target[1])
            
            # Cadeia filtrada com injeção de rastro
            d['chain'] = [(f[2], f"{f[0]}:{f[1]}") for f in py_frames if not any(n in f[0] for n in infra)]

    def _parse_native_crash(self, d: dict, raw: str, exit_code: int):
        """Especialista em C/C++ (Sotéria Engine)."""
        # Isola o bloco de pânico
        match = re.search(r"@(SOTERIA|NEXUS)_BEGIN@(.*?)@(SOTERIA|NEXUS)_END@", raw, re.DOTALL)
        content = match.group(2) if match else raw
        
        # Extrai TAGs em massa
        tags = dict(re.findall(r"TAG_(\w+):\s*(.*)", content))
        
        # Preenche o dossier tático
        d['soteria'] = self._map_registers(tags)
        d['io_history'] = [v for k,v in re.findall(r"TAG_(\w+):\s*(.*)", content) if k == "IO_EVENT"]
        d['inventory'] = re.findall(r"TAG_ARENA_OBJ:\s*(.*?)\s*\|\s*(\d+)\s*bytes", raw)
        
        # Triangulação de Código
        loc = tags.get('RASTRO_LOC', "")
        if ":" in loc:
            f_path, line = loc.rsplit(':', 1)
            d['file'] = self._find_source(f_path)
            d['line'] = int(line) if line.isdigit() else 0

        # Aplica Oráculo de Causa Raiz Nativa (Baseado no crash_signatures.py)
        self._apply_native_logic(d, tags, exit_code)

    def _apply_native_logic(self, d: dict, tags: dict, exit_code: int):
        """Aplica as regras definidas no crash_signatures.py."""
        motivo = tags.get('MOTIVO', '').upper()
        detail = tags.get('DETAIL', '').upper()
        
        from .crash_signatures import NATIVE_LOGIC_PATTERNS
        
        for entry in NATIVE_LOGIC_PATTERNS:
            # Garante que temos pelo menos os 3 campos necessários
            if len(entry) >= 3:
                key, err, exp = entry[0], entry[1], entry[2]
                if key in motivo or key in detail:
                    d['technical_error'] = err
                    d['explanation'] = exp
                    return

        # Fallback para sinais do Windows
        if exit_code in WIN_SIGNALS:
            d['technical_error'], d['explanation'] = WIN_SIGNALS[exit_code]
        
        # 1. Verifica Padrões Vulcan/Sotéria
        for pattern in NATIVE_LOGIC_PATTERNS:
            if any(k in motivo or k in detail for k in pattern['keywords']):
                d['technical_error'] = pattern['error']
                d['explanation'] = pattern['explanation']
                
                # Caso especial para OOM (extração dinâmica de bytes)
                if pattern['id'] == "ARENA_OOM":
                    v_match = re.search(r"Pedido (\d+) bytes", detail, re.IGNORECASE)
                    if v_match: d['explanation'] += f" Falha ao alocar {v_match.group(1)} bytes."
                return

        # 2. Se não for Vulcan, verifica Sinais de Hardware (OS)
        # Converte exit_code para int se for string hex
        try:
            code = int(str(exit_code), 16) if str(exit_code).startswith('0x') else int(exit_code)
            if code in WIN_SIGNALS:
                d['technical_error'], d['explanation'] = WIN_SIGNALS[code]
        except: pass

    def _parse_python(self, d: dict, raw: str):
        """Especialista em Python: Desembrulha Aegis e Triangula o Alvo Real."""
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines: return

        # 1. LIMPEZA DO LAUDO (Unwrap Aegis)
        # Remove prefixos de segurança para chegar na causa raiz real
        last_line = lines[-1]
        clean_msg = re.sub(r'^(RuntimeError: Aegis Sandbox Blocked: |Aegis Sandbox Blocked: |ManualTrigger: )', '', last_line).strip()
        
        # 2. IDENTIFICAÇÃO DO ERRO E EXPLICAÇÃO HUMANA
        # Busca primeiro por "TipoError: mensagem"
        exc_type = "EXCEPTION"
        if ":" in clean_msg:
            exc_type = clean_msg.split(":")[0].strip()
        elif "division by zero" in clean_msg.lower():
            exc_type = "ZeroDivisionError"

        from .crash_signatures import PYTHON_EXCEPTIONS
        if exc_type in PYTHON_EXCEPTIONS:
            d['technical_error'], d['explanation'] = PYTHON_EXCEPTIONS[exc_type]
            # Adiciona a mensagem real entre parênteses para detalhamento
            d['explanation'] += f" ({clean_msg})"
        else:
            d['technical_error'] = exc_type
            d['explanation'] = clean_msg

        # 3. TRIANGULAÇÃO PROFUNDA (Cena do Crime)
        # Captura todos os frames do traceback
        py_frames = re.findall(r'File "(.+?)", line (\d+), in (.+)', raw)
        
        if py_frames:
            # PASC-8.13: Lista negra de arquivos de infraestrutura
            # O Lazarus deve "pular" esses arquivos para achar o código do usuário
            infra_noise = [
                'aegis_utils.py', 'aegis_core.py', 'run.py', 
                'flow_runner.py', 'debug_probe.py', 'contextlib.py',
                'sitecustomize.py', 'lazarus_hook.py'
            ]
            
            # Algoritmo de Escavação: Varre de baixo para cima (do erro para a origem)
            # O primeiro frame que NÃO for infraestrutura é o culpado real.
            target_frame = None
            for frame in reversed(py_frames):
                f_path = frame[0]
                if not any(noise in f_path for noise in infra_noise):
                    target_frame = frame
                    break
            
            # Fallback caso o erro seja na própria infraestrutura
            if not target_frame: 
                target_frame = py_frames[-1]
            
            # Resolve o caminho físico do arquivo (Triangulação Lazarus)
            d['file'] = self._find_source(target_frame[0])
            d['line'] = int(target_frame[1])
            
            # 4. CADEIA DE ENVOLVIMENTO (Filtrada)
            # Mostra apenas o rastro que faz sentido para o desenvolvedor
            d['chain'] = [
                (f[2], f"{f[0]}:{f[1]}") 
                for f in py_frames 
                if not any(n in f[0] for n in infra_noise)
            ]

    def _parse_python_crash(self, d: dict, raw: str):
        """Especialista em Python (Standard Traceback Parser)."""
        # 1. Identificação da Causa Raiz
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines: return

        last_line = lines[-1]
        
        # --- [NOVO] UNWRAP AEGIS ---
        # Se o erro estiver embrulhado pelo Aegis, extrai o conteúdo interno
        if "Aegis Sandbox Blocked:" in last_line:
            last_line = last_line.replace("Aegis Sandbox Blocked:", "").strip()
            # Ex: "division by zero" ou "NameError: name 'y' is not defined"
        if "division by zero" in last_line.lower() and "ZeroDivisionError" not in last_line:
            last_line = "ZeroDivisionError: " + last_line
        
        d['explanation'] = last_line
        
        # Classificação via dicionário
        # Procura por "TipoError: mensagem" ou apenas "mensagem"
        exc_type = "EXCEPTION"
        if ":" in last_line:
            exc_type = last_line.split(":")[0].strip()
        else:
            # Caso o Aegis tenha removido o nome do erro (ex: "division by zero")
            # Tenta inferir pela mensagem
            if "division by zero" in last_line.lower(): exc_type = "ZeroDivisionError"
            elif "not defined" in last_line.lower(): exc_type = "NameError"

        d['technical_error'] = exc_type
        if exc_type in PYTHON_EXCEPTIONS:
            status, laudo = PYTHON_EXCEPTIONS[exc_type]
            d['technical_error'] = status
            d['explanation'] = f"{laudo} ({last_line})"

        # 2. Extração da Cadeia (Frames)
        py_frames = re.findall(r'File "(.+?)", line (\d+), in (.+)', raw)
        if py_frames:
            relevant_frames = [f for f in py_frames if "aegis_utils.py" not in f[0]]
            d['chain'] = [(f[2], f"{f[0]}:{f[1]}") for f in relevant_frames]
            ignore_list = ['run.py', 'aegis_utils.py', 'aegis_core.py', 'contextlib.py']
            project_frames = [f for f in py_frames if not any(x in f[0] for x in ignore_list)]
            blacklist = ['lazarus_hook.py', 'aegis_utils.py', 'run.py', 'contextlib.py', 'bdb.py']
            filtered_frames = [f for f in py_frames if not any(b in f[0] for b in blacklist)]
            target = filtered_frames[-1] if filtered_frames else py_frames[-1]
            d['file'] = self._find_source(target[0])
            d['line'] = int(target[1])

    def _initialize_dossier(self, raw_text: str) -> Dict[str, Any]:
        return {
            'id': hashlib.md5(raw_text.encode()).hexdigest()[:8].upper(),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'technical_error': "UNKNOWN_FAULT",
            'explanation': "Falha não classificada.",
            'file': "NATIVO", 'line': 0, 
            'soteria': {}, 'chain': [], 'inventory': [], 'io_history': []
        }

    def _map_registers(self, tags: dict) -> dict:
        """Isola dados de CPU."""
        regs = {}
        for k, v in tags.items():
            if k.startswith("REG_") or k in ["RIP", "RSP", "RAX", "RBX"]:
                regs[k.replace("REG_", "")] = v
        return regs

    def _init_dossier(self, raw):
        return {
            'id': hashlib.md5(raw.encode()).hexdigest()[:8].upper(),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'technical_error': "SYSTEM_FAULT", 'explanation': "Falha não classificada.",
            'file': "NATIVO", 'line': 0, 'soteria': {}, 'chain': [], 'inventory_raw': []
        }

    def _extract_regs(self, tags):
        return {k.replace("REG_",""): v for k,v in tags.items() if k.startswith("REG_") or k in ["RIP", "RSP"]}

    def _find_source(self, filename: str) -> str:
        if not filename or len(filename) < 3 or filename in ["N/A", "NATIVO"]: return "NATIVO"
        p = Path(filename)
        if p.exists(): return str(p).replace("\\","/")
        try:
            candidates = list(Path(self.root).rglob(p.name))
            return str(candidates[0]).replace("\\","/") if candidates else filename
        except: return filename