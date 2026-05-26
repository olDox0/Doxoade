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

        # 1. Normalização de Protocolos
        raw = raw_text.replace("@NEXUS_END@", "@SOTERIA_END@").replace("@NEXUS_BEGIN@", "@SOTERIA_BEGIN@")
        invocation_str = f"doxoade {' '.join(sys.argv[1:])}"

        chief_heartbeat("LAZARUS", "CRASH_DATA_RECEIVED", {
            "raw_chars": len(raw_text),
            "exit_code": exit_code
        })

        dossier = {
            'id': hashlib.md5(raw.encode()).hexdigest()[:8].upper(),
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'invocation': invocation_str, # <--- ADICIONADO: Corrige o erro de Key
            'technical_error': "SYSTEM_FAULT",
            'explanation': "Falha não classificada.",
            'file': "NATIVO", 'line': 0, 
            'soteria': {}, 'chain': [], 'inventory': [],
            'meta_diag': [] # Log interno de suporte
        }

        # 2. Extração de Tags (Foca no último evento ocorrido)
        blocks = re.findall(r"@SOTERIA_BEGIN@(.*?)@SOTERIA_END@", raw, re.DOTALL)
        inner = blocks[-1] if blocks else raw
        
        # FIX: Captura TODAS as ocorrências de TAG_
        all_tags = re.findall(r"TAG_(\w+):\s*(.*)", inner)
        
        tags = {}
        inventory = []
        for key, val in all_tags:
            k_upper = key.upper()
            if k_upper == "ARENA_OBJ":
                inventory.append(val)
            else:
                tags[k_upper] = val

        dossier['soteria'] = tags
        dossier['inventory_raw'] = inventory

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
