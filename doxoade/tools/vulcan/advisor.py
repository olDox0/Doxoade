# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/advisor.py
"""
Vulcan Advisor - Performance Intelligence v1.0.
Mineração de telemetria Chronos para identificação de Hot-Paths.
Compliance: MPoT-4, PASC-6.4, Aegis-10.
"""
import os
import json
# [DOX-UNUSED] import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from ...database import get_db_connection

class VulcanAdvisor:
    """Consultor de Otimização: Identifica candidatos baseados em fatos (telemetria)."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        # [MODO TESTE]
        self.MIN_HITS = 10         # Aceita rastro nítido
        self.MIN_CPU_PERCENT = 0.0 # Aceita qualquer carga
        self.MAX_FILE_SIZE_KB = 50

    def get_optimization_candidates(self) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # [NEXUS FIX] Busca rastro de 'run' (que agora é in-process), ignorando o exit_code
        query = """
            SELECT line_profile_data, cpu_percent, working_dir 
            FROM command_history 
            ORDER BY id DESC LIMIT 50
        """
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        except Exception as e:
            import logging as _dox_log
            _dox_log.error(f"[INFRA] get_optimization_candidates: {e}")
            return []
        finally: conn.close()
        return self._process_telemetry_data(rows)

    def _process_telemetry_data(self, rows) -> List[Dict[str, Any]]:
        aggregated_hits = {}
        # Normaliza a raiz atual para comparação case-insensitive (Windows)
        current_root = str(self.root).lower().replace('\\', '/')

        for profile_json, cpu, db_work_dir in rows:
            if not profile_json: continue
            data = self._safe_parse_json(profile_json)
            for item in data:
                # [FIX VITAL] Normalização Absoluta de Caminho
                f_raw = item['file'].replace('\\', '/')
                if not os.path.isabs(f_raw):
                    abs_f = os.path.abspath(os.path.join(db_work_dir, f_raw))
                else:
                    abs_f = f_raw
                
                abs_f = abs_f.lower().replace('\\', '/')
                
                # Se o arquivo está na sandbox ou no projeto, nós o aceitamos
                if current_root in abs_f:
                    key = (abs_f, item['line'])
                    aggregated_hits[key] = aggregated_hits.get(key, 0) + item['hits']
        #print(f"aggregated_hits: {aggregated_hits}")
        return self._filter_safe_targets(aggregated_hits)

    def _filter_safe_targets(self, hits_map) -> List[Dict[str, Any]]:
        """Aplica leis de quarentena e segurança (Aegis Shield)."""
        candidates = []
        processed_files = set()

        for (file_path, line), hits in sorted(hits_map.items(), key=lambda x: x[1], reverse=True):
            if hits < self.MIN_HITS or file_path in processed_files:
                continue
            
            # PASC-1.3 & 1.6: Verifica se o arquivo é gerenciável
            if self._is_file_safe_for_vulcan(file_path):
                candidates.append({
                    'file': file_path,
                    'line': line,
                    'hits': hits,
                    'reason': f"Hot-Path detectado ({hits} hits em CPU-Bound)."
                })
                processed_files.add(file_path)

        print(f"candidates: {candidates}")
        return candidates

    def _is_file_safe_for_vulcan(self, file_path: str) -> bool:
        p = Path(file_path).resolve()
        p_str = str(p).lower()
        if not p.exists(): return False
        
        # [AEGIS CORE SHIELD] Protege o Doxoade, mas libera a Sandbox
        if "doxoade/doxoade" in p_str or "doxoade\\doxoade" in p_str:
            return False 
        
        # Libera vulcan_sandbox explicitamente para seus testes
        if "tests" in p_str and "vulcan_sandbox" not in p_str:
            return False
            
        if any(x in p_str for x in ["venv", "lib/"]): return False
        return True

    def _safe_parse_json(self, data):
        try: return json.loads(data)
        except Exception: return [] # [FIX] Restrito

# Instância exportada para o Vulcan Autopilot
vulcan_advisor = VulcanAdvisor(os.getcwd())