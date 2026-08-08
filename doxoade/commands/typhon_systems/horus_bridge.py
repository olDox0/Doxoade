# doxoade/doxoade/commands/typhon_systems/horus_bridge.py
# -*- coding: utf-8 -*-
"""
TYPHON ⇄ HORUS — ponte de observabilidade nativa do Doxoade.

Regras:
• Sempre gravar fallback local em JSONL.
• Tentar usar chief_heartbeat oficial.
• Nunca quebrar o Typhon se o logger oficial estiver indisponível.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

try:
    from doxoade.tools.core_locator import GLOBAL_DATA_DIR
except Exception:
    GLOBAL_DATA_DIR = Path("data")

_LOCAL_HB = GLOBAL_DATA_DIR / "logs" / "typhon_heartbeats.jsonl"


def _write_local(rec: dict) -> bool:
    try:
        _LOCAL_HB.parent.mkdir(parents=True, exist_ok=True)

        with open(_LOCAL_HB, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        return True

    except Exception:
        return False


def _call_chief_heartbeat(subsystem: str, action: str, details: dict) -> bool:
    """
    Importa e chama chief_heartbeat de forma segura.

    Importante:
    - a importação fica isolada;
    - se falhar, retorna False;
    - nunca deixa UnboundLocalError vazar.
    """

    try:
        from doxoade.tools.telemetry_tools.logger import chief_heartbeat

    except Exception:
        return False

    try:
        chief_heartbeat(subsystem, action, details)
        return True

    except Exception:
        return False


def heartbeat(subsystem: str, action: str, details: dict) -> dict:
    details = dict(details or {})

    # Padroniza chave de motivo/failure mode.
    if "f" not in details and "motivo" in details:
        details["f"] = details["motivo"]

    # Evita throttle agressivo do chief_heartbeat.
    if "category" not in details:
        details["category"] = (
            details.get("motivo")
            or details.get("f")
            or action
        )

    # Garante unicidade de evento em auditoria crítica.
    if "nonce" not in details:
        details["nonce"] = uuid.uuid4().hex

    rec = {
        "timestamp": datetime.now().isoformat(),
        "subsystem": subsystem.upper(),
        "action": action.upper(),
        "data": details,
        "pid": os.getpid(),
    }

    rec["local"] = _write_local(rec)
    rec["doxoade"] = _call_chief_heartbeat(
        subsystem.upper(),
        action.upper(),
        details,
    )

    return rec


def read_heartbeats(limit: int = 400):
    recs = []

    if not _LOCAL_HB.exists():
        return recs

    try:
        lines = _LOCAL_HB.read_text(encoding="utf-8", errors="ignore").splitlines()

        for line in lines[-limit:]:
            line = line.strip()

            if not line:
                continue

            try:
                recs.append(json.loads(line))

            except Exception:
                pass

    except Exception:
        pass

    return recs
