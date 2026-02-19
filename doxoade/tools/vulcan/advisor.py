# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/advisor.py (v98.0 Smart-State)
import os
import json
# [DOX-UNUSED] from colorama import Fore
from pathlib import Path
# [DOX-UNUSED] from typing import Any
from ...database import get_db_connection

class VulcanAdvisor:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
        self.MIN_HITS = 3

    def get_optimization_candidates(self) -> list:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Busca rastro térmico
        query = "SELECT line_profile_data, working_dir FROM command_history ORDER BY id DESC LIMIT 100"
        try:
            cursor.execute(query)
            return self._process_telemetry(cursor.fetchall())
        finally: conn.close()

    def _process_telemetry(self, rows):
        aggregated = {}
        for profile_json, db_work_dir in rows:
            if not profile_json: continue
            try:
                for item in json.loads(profile_json):
                    f_raw = item['file'].replace('\\', '/')
                    abs_f = os.path.abspath(os.path.join(db_work_dir, f_raw)) if not os.path.isabs(f_raw) else f_raw
                    if os.path.exists(abs_f):
                        hits = item['hits']
                        # BÔNUS TOOLS: Bibliotecas internas ganham 3x mais prioridade
                        if "tools/" in abs_f.replace('\\', '/'):
                            hits *= 3
                        aggregated[abs_f] = aggregated.get(abs_f, 0) + hits
            except Exception as e:
                import logging as _dox_log
                _dox_log.error(f"[INFRA] _process_telemetry: {e}")
                continue
            
        for abs_f, hits in aggregated.items():
            # Hefesto Boost: Bibliotecas em tools/ ganham bônus de prioridade
            if "tools/" in abs_f.replace('\\', '/'):
                aggregated[abs_f] = hits * 2 
                
        return self._filter_stale_files(aggregated)

    def _filter_stale_files(self, hits_map):
        candidates = []
        for file_path, hits in sorted(hits_map.items(), key=lambda x: x[1], reverse=True):
            if hits < self.MIN_HITS: continue
            
            # PASC-2: Se o binário existe e é mais novo que o fonte, pula.
            if self._is_already_compiled(file_path):
                continue
                
            candidates.append({'file': file_path, 'hits': hits})
        return candidates

    def _is_already_compiled(self, py_path):
        stem = Path(py_path).stem
        ext = ".pyd" if os.name == 'nt' else ".so"
        bins = list(self.bin_dir.glob(f"v_{stem}*{ext}"))
        if not bins: return False
        
        # Compara datas
        latest_bin = max(os.path.getmtime(b) for b in bins)
        return os.path.getmtime(py_path) <= latest_bin