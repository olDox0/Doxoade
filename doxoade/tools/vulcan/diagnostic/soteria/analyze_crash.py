# -*- coding: utf-8 -*-
"""
Córtex Analítico Lazarus v77.0 - O Mapa da Verdade.
Responsabilidade Única: Transformar logs de crash em Dados Estruturados.
"""
import re
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, List

from doxoade.tools.telemetry_tools.logger import chief_heartbeat

# Sinais de Hardware (Windows)
WIN_SIGNALS = {
    3221225477: ("AccessViolation (0xc0000005)", "Tentativa ilegal de violar a RAM física."),
    3221225481: ("DivideByZero", "Erro aritmético de hardware."),
    3221225621: ("StackOverflow", "A pilha de recursão explodiu."),
    3221226505: ("StackBufferOverrun (0xc0000409)", "A integridade da pilha foi destruída (Stack Smashing).")
}

class CrashProcessor:
    def __init__(self, project_root: str):
        self.root = project_root

    def _find_source(self, filename: str) -> str:
        """Localiza o arquivo original no projeto, ignorando pastas de build."""
        from pathlib import Path
        if not filename or len(filename) < 3 or filename == "N/A": return "NATIVO"
        p = Path(filename)
        if p.exists(): return str(p).replace("\\", "/")
        
        # Busca recursiva no projeto
        search_root = Path(self.root)
        candidates = [c for c in search_root.rglob(p.name) if not any(x in str(c).lower() for x in ['.doxoade', 'venv', 'build', 'shadow'])]
        return str(candidates[0]).replace("\\", "/") if candidates else filename

    def process(self, raw_text: str, exit_code: int = None) -> Dict[str, Any]:
        import sys
        
        # 1. Normalização e Isolação do Bloco
        raw = raw_text.replace("@NEXUS_END@", "@SOTERIA_END@").replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@")
        clean_raw = raw_text.encode('ascii', 'ignore').decode('ascii')
        invocation_str = f"doxoade {' '.join(sys.argv[1:])}"
        start_marker = "@SOTERIA_BEGIN@"
        if start_marker in raw:
            raw = raw[raw.rfind(start_marker):] # Foca no último pânico ocorrido

        # --- [VITAL] EXTRAÇÃO ANTECIPADA (Ordem de Percepção) ---
        blocks = re.findall(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", raw, re.DOTALL)
        inner = blocks[-1] if blocks else raw
        all_tags = re.findall(r"TAG_(\w+):\s*(.*)", inner)
        io_history = [val for key, val in all_tags if key.upper() == "IO_EVENT"]
        found_tags = [key.upper() for key, val in all_tags]
        
        # Inicialização das listas para o Pipeline
        tags = {}
        inventory = []
        io_history = []
        steps = []
        
        for key, val in all_tags:
            k_up = key.upper()
            if k_up == "STEP": steps.append(val)
            elif k_up == "IO_EVENT": io_history.append(val)
            elif k_up == "ARENA_OBJ": inventory.append(val)
            elif k_up.startswith("REG_"): 
                reg_name = k_up.replace("REG_", "")
                tags[reg_name] = val
            else: tags[k_up] = val

        # Auditoria de Integridade para o Heartbeat
        expected = ["MOTIVO", "RASTRO_LOC", "LEVEL"]
        missing = [t for t in expected if t not in tags]
        
        chief_heartbeat("PIPELINE", "LAZARUS_PERCEPTION", {
            "raw_size": len(raw_text),
            "steps_count": len(steps),
            "has_hardware": "RIP" in tags,
            "last_step": steps[-1] if steps else "NONE"
        })

        dossier = {
            'id': hashlib.md5(raw.encode()).hexdigest()[:8].upper(),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'invocation': invocation_str,
            'technical_error': "SYSTEM_FAULT",
            'explanation': "Falha não classificada.",
            'file': "NATIVO", 'line': 0, 
            'soteria': tags, 'chain': [], 
            'inventory_raw': inventory, 'io_history': io_history,
            'pipeline_steps': steps # <--- FIX: Agora 'steps' está definido
        }

        # ... resto do código (Oráculo de Causa Raiz e Triangulação) ...
        # (Mantenha sua lógica de "if 'CORRUPTION' in motivo" abaixo)
        
        # [RE-VITAL] Garanta que o motivo e detail sejam lidos de 'tags'
        motivo = tags.get('MOTIVO', '').upper()
        detail = tags.get('DETAIL', '').upper()


        # 2. Distribuição de Dados
        tags = {}
        inventory = []
        io_history = []
        
        for key, val in all_tags:
            k_up = key.upper()
            if k_up == "IO_EVENT":
                io_history.append(val)
            elif k_up == "ARENA_OBJ":
                inventory.append(val)
            elif k_up.startswith("REG_"):
                reg_name = k_up.replace("REG_", "")
                tags[reg_name] = val
#                tags[k_up.replace("REG_", "")] = val
            else:
                tags[k_up] = val

        dossier['io_history'] = io_history # Entrega a linha do tempo
        dossier['soteria'] = tags
        dossier['inventory_raw'] = inventory
        dossier['pipeline_steps'] = steps # Para o rescue.py mostrar

        # 3. Oráculo de Causa Raiz
        motivo = tags.get('MOTIVO', '').upper()
        detail = tags.get('DETAIL', '').upper()
        level = tags.get('LEVEL', '').upper()

        if "CORRUPTION" in motivo or "CORRUPCAO" in detail:
            dossier['technical_error'] = "HadesSentinel: Memory Corruption"
            dossier['explanation'] = "O sistema detectou que dados foram escritos fora do limite permitido (Buffer Overflow/Underflow)."

        if "RACE" in motivo or "CONCURRENCY" in motivo:
            dossier['technical_error'] = "ConcurrencyHazard (RaceCondition)"
            dossier['explanation'] = "Falha de Sincronismo: Acesso simultâneo de threads sem Mutex."
        
        elif "OOM" in detail or "ARENA" in motivo:
            dossier['technical_error'] = "ArenaOverflow (OOM)"
            v_match = re.search(r"Pedido (\d+) bytes, restam (\d+)", detail, re.IGNORECASE)
            req, rem = v_match.groups() if v_match else (0, 0)
            dossier['explanation'] = f"Estouro de Arena: Solicitado {int(req):,} bytes | Disponível: {int(rem):,} bytes."

        elif level == "UNKNOWN_PHENOMENA" or "2038" in raw:
            dossier['technical_error'] = "AnomaliaTemporal (Y2038)"
            dossier['explanation'] = "Interrupção de segurança: Limite de tempo de 32-bits atingido."

        elif exit_code in WIN_SIGNALS:
            dossier['technical_error'], dossier['explanation'] = WIN_SIGNALS[exit_code]

        # 4. Triangulação de Precisão
        dossier['chain'] = re.findall(r"TAG_FRAME: \d+ \| (.*?) \| (.*)", raw)
        loc_raw = tags.get('RASTRO_LOC') or (dossier['chain'][0][1] if dossier['chain'] else None)

        if loc_raw and ":" in loc_raw:
            parts = loc_raw.strip().rsplit(':', 1)
            if len(parts) == 2 and len(parts[0]) > 2:
                dossier['file'] = self._find_source(parts[0])
                dossier['line'] = int(parts[1]) if parts[1].isdigit() else 0

        # 5. Inventário (Aprimoramento do Regex)
        # O C usa %zu para size_t, o Python deve ler como dígitos
#        inventory_raw = re.findall(r"TAG_ARENA_OBJ:\s*(.*?) \| (\d+) bytes", raw_text)
        dossier['inventory'] = re.findall(r"TAG_ARENA_OBJ:\s*(.*?)\s*\|\s*(\d+)\s*bytes", raw_text)
#        dossier['inventory'] = inventory_raw
        
        # LOG DE APOIO: Ajuda a meta-análise a saber se o C descarregou o lixo
        if not dossier['inventory'] and "ARENA" in raw:
            dossier['meta_diag'].append("Aviso: Arena OOM detectado mas inventário não descarregado.")
        
        chief_heartbeat("LAZARUS", "TAGS_EXTRACTED", {
            "found_tags": list(tags.keys()),
            "has_inventory": "ARENA_OBJ" in raw_text,
            "has_hardware": "REG_RIP" in tags
        })
        
        chief_heartbeat("LAZARUS", "DATA_INTEGRITY_CHECK", {
            "items_in_inventory": len(inventory),
            "last_motive": tags.get('MOTIVO')
        })
        
        return dossier
