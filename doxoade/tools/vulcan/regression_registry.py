# doxoade/doxoade/tools/vulcan/regression_registry.py
"""
RegressionRegistry
==================
Memória persistente de regressões de performance do Vulcan.

Ciclo de vida de uma função:
  ┌─────────────────────────────────────────────────────────────────┐
  │  (sem registro)                                                 │
  │       │  speedup < min_speedup — 1ª vez                        │
  │       ▼                                                         │
  │  retry_aggressive  ──── speedup OK ────► REMOVIDA (promovida)  │
  │       │  speedup < min_speedup — 2ª vez                        │
  │       ▼                                                         │
  │   excluded  ◄── não compilada em ignites futuros               │
  └─────────────────────────────────────────────────────────────────┘

Chave estável: sha256(abs_path)[:8]:{func_name}
Arquivo:       .doxoade/vulcan/regression_registry.json
"""
from __future__ import annotations
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Dict, FrozenSet, Optional
STATUS_AGGRESSIVE = 'retry_aggressive'
STATUS_EXCLUDED = 'excluded'
MIN_SPEEDUP_DEFAULT = 1.1
_REGISTRY_FILE = 'regression_registry.json'

class RegressionEntry:
    __slots__ = ('file_path', 'func_name', 'speedup', 'attempts', 'status', 'last_updated')

    def __init__(self, file_path: str, func_name: str, speedup: float, attempts: int=1, status: str=STATUS_AGGRESSIVE, last_updated: float=0.0):
        self.file_path = str(Path(file_path).resolve())
        self.func_name = func_name
        self.speedup = speedup
        self.attempts = attempts
        self.status = status
        self.last_updated = last_updated or time.time()

    def to_dict(self) -> dict:
        return {'file_path': self.file_path, 'func_name': self.func_name, 'speedup': round(self.speedup, 4), 'attempts': self.attempts, 'status': self.status, 'last_updated': self.last_updated}

    @classmethod
    def from_dict(cls, d: dict) -> 'RegressionEntry':
        return cls(file_path=d['file_path'], func_name=d['func_name'], speedup=d['speedup'], attempts=d.get('attempts', 1), status=d.get('status', STATUS_AGGRESSIVE), last_updated=d.get('last_updated', 0.0))

    def __repr__(self) -> str:
        return f'RegressionEntry({self.func_name!r}, speedup={self.speedup:.2f}x, attempts={self.attempts}, status={self.status!r})'

class RegressionRegistry:
    """
    Gerencia o histórico persistente de regressões de performance.

    Uso rápido:

        registry = RegressionRegistry(project_root)

        # antes de compilar — filtra candidatos
        excluded   = registry.excluded_funcs_for_file(str(py_file))
        aggressive = registry.aggressive_funcs_for_file(str(py_file))

        # após benchmark — aprende com os resultados
        summary = registry.update_from_benchmark(results, min_speedup=1.1)
        registry.save()
    """

    def __init__(self, project_root: 'str | Path'):
        self.root = Path(project_root).resolve()
        self._path = self.root / '.doxoade' / 'vulcan' / _REGISTRY_FILE
        self._data: Dict[str, RegressionEntry] = {}
        self._load()

    @staticmethod
    def make_key(file_path: str, func_name: str) -> str:
        h = hashlib.sha256(str(Path(file_path).resolve()).encode()).hexdigest()[:8]
        return f'{h}:{func_name}'

    @staticmethod
    def _file_prefix(file_path: str) -> str:
        return hashlib.sha256(str(Path(file_path).resolve()).encode()).hexdigest()[:8]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding='utf-8'))
            self._data = {k: RegressionEntry.from_dict(v) for k, v in raw.items()}
        except Exception:
            self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._path.write_text(json.dumps({k: v.to_dict() for k, v in self._data.items()}, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

    def is_excluded(self, file_path: str, func_name: str) -> bool:
        e = self._data.get(self.make_key(file_path, func_name))
        return e is not None and e.status == STATUS_EXCLUDED

    def needs_aggressive(self, file_path: str, func_name: str) -> bool:
        e = self._data.get(self.make_key(file_path, func_name))
        return e is not None and e.status == STATUS_AGGRESSIVE

    def excluded_funcs_for_file(self, file_path: str) -> FrozenSet[str]:
        prefix = self._file_prefix(file_path)
        return frozenset((e.func_name for k, e in self._data.items() if k.startswith(f'{prefix}:') and e.status == STATUS_EXCLUDED))

    def aggressive_funcs_for_file(self, file_path: str) -> FrozenSet[str]:
        prefix = self._file_prefix(file_path)
        return frozenset((e.func_name for k, e in self._data.items() if k.startswith(f'{prefix}:') and e.status == STATUS_AGGRESSIVE))

    def get_entry(self, file_path: str, func_name: str) -> Optional[RegressionEntry]:
        return self._data.get(self.make_key(file_path, func_name))

    def has_any(self) -> bool:
        return bool(self._data)

    def record_regression(self, file_path: str, func_name: str, speedup: float) -> str:
        """
        Registra regressão. Retorna novo status.
        1ª vez → retry_aggressive
        2ª vez → excluded
        """
        key = self.make_key(file_path, func_name)
        existing = self._data.get(key)
        if existing is None:
            entry = RegressionEntry(file_path=file_path, func_name=func_name, speedup=speedup, attempts=1, status=STATUS_AGGRESSIVE)
        else:
            entry = existing
            entry.speedup = speedup
            entry.attempts += 1
            entry.last_updated = time.time()
            entry.status = STATUS_EXCLUDED if entry.attempts >= 2 else STATUS_AGGRESSIVE
        self._data[key] = entry
        return entry.status

    def record_success(self, file_path: str, func_name: str) -> bool:
        """Remove do registry se estava lá (função promovida). Retorna True se foi promovida."""
        key = self.make_key(file_path, func_name)
        if key in self._data:
            del self._data[key]
            return True
        return False

    def update_from_benchmark(self, results, min_speedup: float=MIN_SPEEDUP_DEFAULT) -> dict:
        """
        Recebe resultados do benchmark e atualiza o registry.
        Retorna resumo com contagens.
        """
        summary = {'excluded': 0, 'retry_aggressive': 0, 'promoted': 0, 'ok': 0}
        for file_res in results:
            fp = file_res.file_path
            for func in file_res.functions:
                if getattr(func, 'status', None) != 'OK' or func.speedup is None:
                    continue
                if func.speedup >= min_speedup:
                    promoted = self.record_success(fp, func.func_name)
                    summary['promoted' if promoted else 'ok'] += 1
                else:
                    new_status = self.record_regression(fp, func.func_name, func.speedup)
                    summary['retry_aggressive' if new_status == STATUS_AGGRESSIVE else 'excluded'] += 1
        self.save()
        return summary

    def clear_excluded(self) -> int:
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if v.status != STATUS_EXCLUDED}
        self.save()
        return before - len(self._data)

    def clear_all(self) -> int:
        n = len(self._data)
        self._data = {}
        self.save()
        return n

    def purge_missing_files(self) -> int:
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if Path(v.file_path).exists()}
        self.save()
        return before - len(self._data)

    def report(self) -> dict:
        counts = Counter((e.status for e in self._data.values()))
        return {'total': len(self._data), 'excluded': counts.get(STATUS_EXCLUDED, 0), 'retry_aggressive': counts.get(STATUS_AGGRESSIVE, 0), 'registry_path': str(self._path), 'entries': sorted([e.to_dict() for e in self._data.values()], key=lambda x: x['speedup'])}

    def render_cli(self) -> None:
        """Imprime relatório colorido no terminal."""
        R = '\x1b[31m'
        Y = '\x1b[33m'
        G = '\x1b[32m'
        C = '\x1b[36m'
        DIM = '\x1b[2m'
        B = '\x1b[1m'
        RST = '\x1b[0m'
        r = self.report()
        print(f'\n{B}{C}  ⬡ VULCAN — REGRESSION REGISTRY{RST}')
        print(f"  Arquivo : {DIM}{r['registry_path']}{RST}")
        print(f"  Total   : {r['total']} entrada(s)   {R}Excluídas: {r['excluded']}{RST}   {Y}Retry-Agressivo: {r['retry_aggressive']}{RST}")
        if not r['entries']:
            print(f'\n  {G}✔ Nenhuma regressão registrada.{RST}\n')
            return
        print(f"\n  {'FUNÇÃO':<38} {'SPEEDUP':>8}  {'STATUS':<20} {'TENTATIVAS':>10}  ARQUIVO")
        print(f"  {'─' * 38} {'─' * 8}  {'─' * 20} {'─' * 10}  {'─' * 30}")
        for e in r['entries']:
            color = R if e['status'] == STATUS_EXCLUDED else Y
            fname = Path(e['file_path']).name[:30]
            print(f"  {e['func_name']:<38} {color}{e['speedup']:>7.2f}x{RST}  {color}{e['status']:<20}{RST} {e['attempts']:>10}  {DIM}{fname}{RST}")
        print()
