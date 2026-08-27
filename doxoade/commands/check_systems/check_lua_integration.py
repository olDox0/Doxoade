# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/check_lua_integration.py
"""
🌉 MA'AT AUDIT <-> LITE XL LUA BRIDGE.
Exporta achados de auditoria em contratos nativos Lua (.lua) e JSON (.json)
para consumo direto pelo template 15_audit_highlighter.lua do Lite XL.
"""
from __future__ import annotations
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from doxoade.tools.lua_systems.lua_bridge import write_lua_bridge_file


def signal_litexl_audit(
    target_file: str,
    findings: List[Dict[str, Any]],
    project_root: str,
    summary: Optional[Dict[str, int]] = None,
) -> Path:
    """Exporta o relatório do Tribunal de Ma'at no contrato bridge do Lite XL."""
    bridge_dir = Path(project_root) / ".doxoade"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    abs_target = os.path.abspath(target_file).replace("\\", "/")
    try:
        rel_target = os.path.relpath(target_file, project_root).replace("\\", "/")
    except ValueError:
        rel_target = abs_target

    formatted_findings = []
    for f in findings:
        ln = f.get("line", 0)
        if ln > 0:
            formatted_findings.append({
                "line": ln,
                "severity": str(f.get("severity", "WARNING")).upper(),
                "category": str(f.get("category", "STYLE")).upper(),
                "message": str(f.get("message", "No message")),
                "suggestion": str(
                    f.get("suggestion_content", "")
                    or f.get("suggestion_action", "")
                    or ""
                ),
            })

    payload = {
        "protocol": "Doxoade-LXL-Audit-v1",
        "timestamp": time.time(),
        "project_root": str(project_root).replace("\\", "/"),
        "active_file": abs_target,
        "relative_file": rel_target,
        "summary": summary
        or {
            "total": len(formatted_findings),
            "errors": sum(
                1
                for x in formatted_findings
                if x["severity"] in ("ERROR", "CRITICAL")
            ),
            "warnings": sum(
                1 for x in formatted_findings if x["severity"] == "WARNING"
            ),
            "info": sum(
                1
                for x in formatted_findings
                if x["severity"] not in ("ERROR", "CRITICAL", "WARNING")
            ),
        },
        "findings": formatted_findings,
    }

    # 1. Contrato Nativo Lua (Carregado a 60 FPS via dofile)
    lua_bridge_path = bridge_dir / "check_bridge.lua"
    write_lua_bridge_file(lua_bridge_path, payload, return_export=True)

    json_bridge_path = bridge_dir / "check_bridge.json"
    temp_json = json_bridge_path.with_suffix(f".tmp_{os.getpid()}")
    temp_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_json.replace(json_bridge_path)

    # 🛡️ Emite o marcador TRUSTED exigido pelo 15_audit_highlighter.lua
    trust_marker = bridge_dir / "TRUSTED"
    trust_marker.write_text("DOXOADE_MAAT_TRUSTED_V1\n", encoding="utf-8")

    return lua_bridge_path
