# doxoade/doxoade/tools/vulcan/advisor.py
import re
import os, json, hashlib
from pathlib import Path
from collections import defaultdict
from doxoade.database import get_db_connection

class VulcanAdvisor:

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.bin_dir = self.root / '.doxoade' / 'vulcan' / 'bin'
        self.MIN_HITS = 3

    def get_optimization_candidates(self, force: bool=False) -> list:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = 'SELECT line_profile_data, working_dir FROM command_history ORDER BY id DESC LIMIT 100'
        try:
            cursor.execute(query)
            return self._process_telemetry(cursor.fetchall(), force)
        finally:
            conn.close()

    def _process_telemetry(self, rows, force: bool) -> list:
        aggregated = {}
        for profile_json, db_work_dir in rows:
            if not profile_json:
                continue
            try:
                for item in json.loads(profile_json):
                    f_raw = item['file'].replace('\\\\', '/')
                    abs_f = os.path.abspath(os.path.join(db_work_dir, f_raw))
                    if os.path.exists(abs_f):
                        aggregated[abs_f] = aggregated.get(abs_f, 0) + item['hits']
            except Exception:
                continue
        candidates = []
        for file_path, hits in sorted(aggregated.items(), key=lambda x: x[1], reverse=True):
            if hits < self.MIN_HITS:
                continue
            if not force and self._is_already_compiled(file_path):
                continue
            candidates.append({'file': file_path, 'hits': hits})
        return candidates

    def _is_already_compiled(self, py_path: str) -> bool:
        abs_path = Path(py_path).resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        pattern = f'v_{abs_path.stem}_{path_hash}*'
        ext = '.pyd' if os.name == 'nt' else '.so'
        bins = list(self.bin_dir.glob(f'{pattern}{ext}'))
        if not bins:
            return False
        latest_bin_mtime = max((os.path.getmtime(b) for b in bins))
        return os.path.getmtime(py_path) <= latest_bin_mtime

    def get_hot_dependencies(self) -> dict:
        """Analisa a telemetria e retorna um dict de bibliotecas de terceiros com mais 'hits'."""
        conn = get_db_connection()
        cursor = conn.cursor()
        query = 'SELECT line_profile_data, working_dir FROM command_history WHERE line_profile_data IS NOT NULL ORDER BY id DESC LIMIT 200'
        hot_libs = defaultdict(int)
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            for profile_json, db_work_dir in rows:
                try:
                    for item in json.loads(profile_json):
                        f_raw = item['file'].replace('\\\\', '/')
                        if 'site-packages' not in f_raw:
                            continue
                        match = re.search('site-packages[\\\\\\\\/]([^\\\\\\\\/]+)', f_raw)
                        if match:
                            lib_name = match.group(1)
                            if not lib_name.startswith('_'):
                                hot_libs[lib_name] += item['hits']
                except (json.JSONDecodeError, KeyError):
                    continue
        finally:
            conn.close()
        return dict(sorted(hot_libs.items(), key=lambda item: item[1], reverse=True))