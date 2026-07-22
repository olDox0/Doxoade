# doxoade/tools/hermes_systems/hbc6_audit.py
"""
HBC6 Audit Trail — Diagnóstico de Fallback do Hermes
Ativação:
    set HERMES_HBC6_AUDIT=1        (Windows CMD)
    $env:HERMES_HBC6_AUDIT=1       (PowerShell)
"""
import os
import time
import json
import threading
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime


class HBC6Decision(Enum):
    """Todas as decisões possíveis no pipeline HBC6."""
    MOTOR_C_HIT = "MOTOR_C_HIT"
    MARSHAL_HIT = "MARSHAL_HIT"
    LZ4_HIT = "LZ4_HIT"
    FALLBACK_BLACKLIST = "FB_BLACKLIST"
    FALLBACK_NO_HBC6 = "FB_NO_HBC6"
    FALLBACK_HASH_MISMATCH = "FB_HASH"
    FALLBACK_C_BRIDGE_NULL = "FB_C_NULL"
    FALLBACK_C_BRIDGE_EXC = "FB_C_EXC"
    FALLBACK_MARSHAL_EXC = "FB_MARSHAL"
    FALLBACK_NOT_DOXOADE = "FB_NOT_DOX"
    FALLBACK_IMPORT_ERROR = "FB_IMPORT"
    SKIP_BUILTIN = "SKIP_BUILTIN"
    SKIP_FROZEN = "SKIP_FROZEN"


@dataclass
class HBC6AuditEntry:
    timestamp_ms: float
    module_name: str
    decision: str
    reason: str
    py_path: Optional[str] = None
    hbc6_path: Optional[str] = None
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    elapsed_us: float = 0.0
    exception_msg: Optional[str] = None
    fallback_to: str = "N/A"
    thread_id: int = 0

    def is_fallback(self) -> bool:
        return self.decision.startswith("FB_") or self.decision.startswith("SKIP_")


class HBC6Auditor:
    _instance: Optional['HBC6Auditor'] = None
    _lock = threading.Lock()

    def __init__(self):
        self.entries: List[HBC6AuditEntry] = []
        self._start_time = time.perf_counter()
        self._enabled = os.environ.get("HERMES_HBC6_AUDIT", "0") == "1"
        self._verbose = os.environ.get("HERMES_HBC6_AUDIT_VERBOSE", "0") == "1"
        self._lock_entries = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'HBC6Auditor':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record(self, module_name, decision, reason="", py_path=None,
               hbc6_path=None, expected_hash=None, actual_hash=None,
               elapsed_us=0.0, exception_msg=None, fallback_to="N/A"):
        if not self._enabled:
            return

        entry = HBC6AuditEntry(
            timestamp_ms=(time.perf_counter() - self._start_time) * 1000,
            module_name=module_name,
            decision=decision.value,
            reason=reason,
            py_path=py_path,
            hbc6_path=hbc6_path,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            elapsed_us=elapsed_us,
            exception_msg=exception_msg,
            fallback_to=fallback_to,
            thread_id=threading.current_thread().ident or 0,
        )

        with self._lock_entries:
            self.entries.append(entry)

        if self._verbose:
            icon = "✔" if not entry.is_fallback() else "⚠"
            color = "\033[92m" if not entry.is_fallback() else "\033[93m"
            reset = "\033[0m"
            print(
                f"  {color}{icon} [HBC6]{reset} "
                f"{entry.timestamp_ms:>8.2f}ms │ "
                f"{module_name:<45} │ "
                f"{decision.value:<16} │ "
                f"{reason[:60]}"
            )

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.entries)
        if total == 0:
            return {"total": 0, "message": "Nenhum módulo interceptado."}

        hits = [e for e in self.entries if not e.is_fallback()]
        fallbacks = [e for e in self.entries if e.is_fallback()]

        fb_by_reason: Dict[str, List[str]] = {}
        for e in fallbacks:
            fb_by_reason.setdefault(e.decision, []).append(e.module_name)

        hit_times = [e.elapsed_us for e in hits if e.elapsed_us > 0]
        fb_times = [e.elapsed_us for e in fallbacks if e.elapsed_us > 0]

        return {
            "total_modules_intercepted": total,
            "hbc6_hits": len(hits),
            "fallbacks": len(fallbacks),
            "hit_rate_pct": round((len(hits) / total) * 100, 1) if total else 0,
            "avg_hit_time_us": round(sum(hit_times) / len(hit_times), 2) if hit_times else 0,
            "avg_fallback_time_us": round(sum(fb_times) / len(fb_times), 2) if fb_times else 0,
            "fallback_breakdown": {
                reason: {"count": len(mods), "modules": mods[:10]}
                for reason, mods in sorted(fb_by_reason.items(), key=lambda x: -len(x[1]))
            },
            "session_duration_ms": round((time.perf_counter() - self._start_time) * 1000, 2),
        }

    def print_report(self):
        summary = self.get_summary()
        if summary["total_modules_intercepted"] == 0:
            print("\n  ⚠ [HBC6-AUDIT] Nenhum módulo foi interceptado.")
            return

        print(f"\n{'─' * 72}")
        print(f"  📊 HBC6 AUDIT REPORT")
        print(f"{'─' * 72}")
        print(f"  Total Interceptados : {summary['total_modules_intercepted']}")
        print(f"  HBC6 Hits (Motor C) : {summary['hbc6_hits']}")
        print(f"  Fallbacks           : {summary['fallbacks']}")
        print(f"  Hit Rate            : {summary['hit_rate_pct']}%")
        print(f"  Tempo médio (hit)   : {summary['avg_hit_time_us']} µs")
        print(f"  Tempo médio (fb)    : {summary['avg_fallback_time_us']} µs")
        print(f"  Duração da sessão   : {summary['session_duration_ms']} ms")

        if summary["fallback_breakdown"]:
            print(f"\n  ⚠ FALLBACKS POR RAZÃO:")
            for reason, data in summary["fallback_breakdown"].items():
                print(f"    [{data['count']:>3}x] {reason}")
                for mod in data["modules"][:5]:
                    print(f"          └─ {mod}")
                if data["count"] > 5:
                    print(f"          └─ ... e mais {data['count'] - 5}")

        print(f"{'─' * 72}\n")

    def dump_json(self, output_path=None):
        if output_path is None:
            output_path = str(Path.cwd() / ".doxoade" / "hermes" / "hbc6_audit.json")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "entries": [asdict(e) for e in self.entries],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path