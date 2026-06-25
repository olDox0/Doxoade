# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/analyze_crash.py
"""
Córtex Analítico Lazarus v77.2 - O Mapa da Verdade.
Arquitetura: Multi-Language Dispatcher c/ Isolamento de Assinaturas.
"""
import os  # [FIX] ausente: usado em archive_crash_to_hades_vulcan_optimized (os.getcwd)
import re
import hashlib
import datetime
# [DOX-UNUSED] import sys
from pathlib import Path
from typing import Dict, Any

from .crash_signatures import WIN_SIGNALS, PYTHON_EXCEPTIONS
# [DOX-UNUSED] from doxoade.tools.telemetry_tools.logger import chief_heartbeat
# [DOX-UNUSED] from .python_diagnostics import diagnose_python_error
from .native_diagnostics import diagnose_native_error

from doxoade.tools.alexandria.engine import alexandria_write
def archive_crash_to_hades_vulcan_optimized(nx_data):
    """
    Sincroniza o crash com a tabela de incidentes para que
    'doxoade search' ou 'doxoade log' encontrem a falha.
    """
    from doxoade.core_database import get_db_connection
    import datetime as _dt
    
    conn = get_db_connection()
    # nx_data aqui contém o dossiê completo
    verdict = nx_data.get('technical_error', 'NATIVE_FAULT')
    explanation = nx_data.get('explanation', 'Crash detectado pela Sotéria.')
    
    alexandria_write('''
        INSERT OR REPLACE INTO open_incidents 
        (finding_hash, file_path, line, message, category, timestamp, project_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        nx_data.get('id'), # Hash do Evento
        nx_data.get('file'),
        nx_data.get('line'),
        f"[{verdict}] {explanation}",
        "CRASH-FORENSIC",
        _dt.datetime.now().isoformat(),
        os.getcwd()
    ))
    conn.commit()
    conn.close()

class CrashProcessor:
    def __init__(self, project_root: str):
        self.root = project_root

    def process(self, raw_text: str, exit_code: int = None) -> Dict[str, Any]:
        d = self._init_dossier(raw_text)
        if exit_code is not None:
            d['exit_code'] = exit_code
            
        if exit_code and (exit_code > 255 or exit_code < 0):
             # O código em native_diagnostics já lida com hexadecimais
             pass 
        
        if "SystemExit" in raw_text:
            d['technical_error'] = "NORMAL_EXIT"
            return d
        if "@SOTERIA_BEGIN@" in raw_text or "TAG_MOTIVO" in raw_text:
            self._parse_native(d, raw_text, exit_code)
        elif "Traceback" in raw_text:
            self._parse_python(d, raw_text)
        return d

    def _parse_native(self, d: dict, raw: str, exit_code: int):
        match = re.search(r"@(SOTERIA|NEXUS)_BEGIN@(.*?)@(SOTERIA|NEXUS)_END@", raw, re.DOTALL)
        content = match.group(2) if match else raw
        tags = dict(re.findall(r"TAG_(\w+):\s*(.*)", content))
        d['soteria'] = {k.replace("REG_",""): v for k,v in tags.items() if k.startswith("REG_") or k in ["RIP", "RSP", "RAX", "FAULT_ADDR"]}
        d['technical_error'], d['explanation'] = diagnose_native_error(exit_code, tags)
        loc = tags.get('RASTRO_LOC', "") or (re.findall(r"TAG_FRAME: 0 \| .*? \| (.*)", raw) or [""])[0]
        if loc and ":" in loc:
            f_path, line = loc.rsplit(':', 1)
            # LIMPEZA CRÍTICA: Se for um arquivo da pasta .doxoade (shadow), 
            # pegamos apenas o nome para o Lazarus achar o original no src/
            if ".doxoade" in f_path.lower() or "shadow" in f_path.lower():
                f_path = Path(f_path).name
            d['file'] = self._find_source(f_path)
            d['line'] = int(line) if line.isdigit() else 0
        d['chain'] = re.findall(r"TAG_FRAME: \d+ \| (.*?) \| (.*)", content)
        d['inventory'] = re.findall(r"TAG_ARENA_OBJ:\s*(.*?)\s*\|\s*(\d+)\s*bytes", raw)
        # 2. Captura de IO (Tudo que foi trackeado pela Sotéria)s
        # Buscamos tanto TAG_IO_EVENT quanto mensagens marcadas
        d['io_history'] = re.findall(r"TAG_IO_EVENT:\s*(.*)", raw)
        # Se o IO_EVENT estiver vazio, tentamos pegar linhas de rastro manual
        if not d['io_history']:
            d['io_history'] = re.findall(r"■\s*\[VETOR.*?\]\s*(.*)", raw)

    # [FIX] _parse_python estava definido duas vezes. Python usava silenciosamente
    # apenas a segunda definição (linha ~185), tornando esta letra morta.
    # A versão completa foi mantida abaixo. Esta foi removida.

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
        d['io_history'] = [v for k,v in re.findall(r"TAG_(\w+):\s*(.*)", raw) if k == "IO_EVENT"]
        
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

        # NATIVE_LOGIC_PATTERNS são tuplas: (keyword_str, error_label, explanation)
        # [FIX] Bloco anterior tentava acessar pattern['keywords'], pattern['error'],
        # pattern['id'] como dict — crashava com TypeError. Removido.
        for key_str, error_label, explanation in NATIVE_LOGIC_PATTERNS:
            if key_str in motivo or key_str in detail:
                d['technical_error'] = error_label
                d['explanation'] = explanation
                break

        # Fallback: Sinais de Hardware Windows (exit_code numérico ou hex)
        try:
            code = int(str(exit_code), 16) if str(exit_code).startswith('0x') else int(exit_code)
            if code in WIN_SIGNALS:
                status, expl = WIN_SIGNALS[code]
                d['technical_error'] = status
                d['explanation'] = expl
        except Exception:
            pass

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

    # [FIX] _initialize_dossier era dead code (nunca chamada — process() chama _init_dossier).
    # Os campos extras que ela tinha (inventory, io_history) foram incorporados em _init_dossier.

    def _map_registers(self, tags: dict) -> dict:
        """Isola dados de CPU."""
        regs = {}
        for k, v in tags.items():
            if k.startswith("REG_") or k in ["RIP", "RSP", "RAX", "RBX"]:
                regs[k.replace("REG_", "")] = v
        return regs

    def _init_dossier(self, raw: str) -> Dict[str, Any]:
        """Cria o dossiê inicial com todos os campos esperados pelos parsers."""
        return {
            'id': hashlib.md5(raw.encode()).hexdigest()[:8].upper(),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'technical_error': "SYSTEM_FAULT",
            'explanation': "Falha não classificada.",
            'file': "NATIVO", 'line': 0,
            'soteria': {}, 'chain': [],
            # [FIX] inventory_raw renomeado para inventory (usado por _parse_native e rescue.py)
            # io_history adicionado (ausente na versão antiga de _init_dossier)
            'inventory': [], 'io_history': [],
        }

    def _extract_regs(self, tags):
        return {k.replace("REG_",""): v for k,v in tags.items() if k.startswith("REG_") or k in ["RIP", "RSP"]}

    def _find_source(self, filename: str) -> str:
        """Triangulação Lazarus: Resolve caminhos reais ocultando a infraestrutura."""
        if not filename or len(filename) < 3 or filename in ["N/A", "NATIVO"]: return "NATIVO"
        if ".doxoade" in filename.replace("\\", "/"): filename = Path(filename).name
        p = Path(filename)
        if p.exists(): return str(p).replace("\\","/")
        try:
            candidates = [c for c in Path(self.root).rglob(p.name) 
                         if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build'])]
            return str(candidates[0]).replace("\\","/") if candidates else filename
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f"[INFRA] _find_source: {e}")
            return filename

    def _cross_reference_hades(self, d: dict, pid: str):
        """Busca no Hades quem foi o mestre Python deste processo."""
        try:
            from doxoade.core_database import get_db_connection
            import json
            conn = get_db_connection()
            # Busca a última chamada VULCAN deste PID (limite de 10 segundos)
            query = """
                SELECT data FROM operational_logs 
                WHERE pid = ? AND subsystem = 'VULCAN'
                AND timestamp > datetime('now', '-10 seconds')
                ORDER BY timestamp DESC LIMIT 1
            """
            row = conn.execute(query, (pid,)).fetchone()
            conn.close()
            if row:
                ctx = json.loads(row['data']).get('caller_context')
                if ctx:
                    # Injeta o frame Python como origem da chain
                    d['chain'].insert(0, (f"PYTHON_INVOKER: {ctx['func']}", f"{ctx['file']}:{ctx['line']}"))
                    d['explanation'] += f"\n[BRIDGE] Acionado por: {ctx['func']}() em {ctx['file']}"
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f"[INFRA] _cross_reference_hades: {e}")
