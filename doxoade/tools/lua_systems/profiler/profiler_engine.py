# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/profiler/profiler_engine.py
"""
Motor de Análise de Gargalos e Diagnóstico Hierárquico por Arquivo (Chronos Deep Dissector).
"""
from __future__ import annotations
import json
import statistics
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from .profiler_schema import ProfilerReport, BootMetric, FrameMetric, ThreadMetric


MODULE_COST_FACTORS = {
    "00_01_api_probe.lua": "Varredura e resolução dinâmica de 54 contratos de API",
    "11_tab_context_menu.lua": "Closures de menu, fuzzy matcher e cálculo de caminhos",
    "06_tree_manager.lua": "Normalizador de caminhos no disco e gerador de diretórios",
    "01_ipc_dispatcher.lua": "Varredura e parsing de sovereign_session.lua e fila IPC",
    "04_color_and_search_highlight.lua": "Compilação de regex de syntax Python e highlight multiline",
    "15_audit_highlighter.lua": "Parsing de severidades e buffers de auditoria Ma'at",
    "00_header_and_logger.lua": "Inicialização de logger, stubs de SO e polyfills C",
    "03_tab_colors.lua": "Hash determinístico de projetos e hooks do Node",
    "14_doxnote_panel.lua": "Parser regex de tarefas, datas relativas e IDs de notas",
    "08_pot_panel.lua": "Gramática Markdown para linguagens múltiplas (Dumppot)",
    "13_toolbar_doxoade.lua": "Registro de itens de statusview assíncronos",
}


class ProfilerEngine:
    """Analisador de Telemetria e Hotspots do Lite XL."""

    @staticmethod
    def get_telemetry_file(user_dir: Optional[Path] = None) -> Path:
        if user_dir is None:
            user_dir = Path.home() / ".config" / "lite-xl"
        return user_dir / ".doxoade" / "diagnostics" / "profiler_telemetry.json"

    @classmethod
    def load_report(cls, user_dir: Optional[Path] = None) -> Optional[ProfilerReport]:
        t_file = cls.get_telemetry_file(user_dir)
        if not t_file.exists():
            return None
        try:
            raw = json.loads(t_file.read_text(encoding="utf-8"))
            return ProfilerReport.from_dict(raw)
        except Exception:
            return None

    @classmethod
    def run_deep_benchmark(cls, runs: int = 5, target_file: Optional[str] = None) -> Dict[str, Any]:
        """Executa benchmark estatístico agrupando funções hierarquicamente por arquivo."""
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

        harness_path = LiteXLEngine.get_shadow_harness_path()
        templates = LiteXLEngine.get_template_files()
        runtime_info = LiteXLEngine.lua_runtime_info()

        if not runtime_info or not harness_path.exists() or not templates:
            return {"runs": 0, "total_avg_ms": 0.0, "modules": []}

        lua_exe, _ = runtime_info
        cmd = [str(lua_exe), str(harness_path)] + [str(t) for t in templates]

        all_runs: Dict[str, List[float]] = {}
        mem_stats: Dict[str, float] = {}
        file_funcs: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for _ in range(runs):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            output = proc.stdout

            in_mod_report = False
            in_func_report = False

            for line in output.splitlines():
                line = line.strip()
                if line == "=== SHADOW_REPORT_START ===":
                    in_mod_report = True; continue
                elif line == "=== SHADOW_REPORT_END ===":
                    in_mod_report = False; continue
                elif line == "=== FUNCTION_REPORT_START ===":
                    in_func_report = True; continue
                elif line == "=== FUNCTION_REPORT_END ===":
                    in_func_report = False; continue

                if in_mod_report and "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        fname = parts[1]
                        t_ms = float(parts[2])
                        mem_kb = float(parts[3]) if len(parts) > 3 else 0.0
                        all_runs.setdefault(fname, []).append(t_ms)
                        mem_stats[fname] = mem_kb

                elif in_func_report and "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 6:
                        src = parts[0].replace("@", "")
                        name = parts[1] if parts[1] != "anonymous" else f"closure:L{parts[2]}"
                        line_no = int(parts[2])
                        calls = int(parts[3])
                        self_t = float(parts[4])
                        total_t = float(parts[5])

                        file_funcs.setdefault(src, {})
                        key = f"{name}:{line_no}"
                        if key not in file_funcs[src]:
                            file_funcs[src][key] = {
                                "name": name,
                                "line": line_no,
                                "calls": 0,
                                "self_time_ms": 0.0,
                                "total_time_ms": 0.0
                            }
                        file_funcs[src][key]["calls"] += calls
                        file_funcs[src][key]["self_time_ms"] += (self_t / runs)
                        file_funcs[src][key]["total_time_ms"] += (total_t / runs)

        aggregated_mods = []
        total_avg_time = 0.0

        for fname, times in all_runs.items():
            if target_file and target_file.lower() not in fname.lower():
                continue

            mean_time = statistics.mean(times)
            total_avg_time += mean_time

            # Agrupa e ordena as funções internas do arquivo
            funcs = list(file_funcs.get(fname, {}).values())
            funcs.sort(key=lambda f: f["total_time_ms"], reverse=True)

            # Calcula a contribuição percentual de cada função no arquivo
            file_time_safe = max(mean_time, 0.001)
            dominant_func = funcs[0] if funcs else None
            is_single_bottleneck = (dominant_func and (dominant_func["total_time_ms"] / file_time_safe) >= 0.50)

            for f in funcs:
                f["file_percent"] = (f["total_time_ms"] / file_time_safe) * 100

            aggregated_mods.append({
                "module": fname,
                "mean_ms": mean_time,
                "mem_kb": mem_stats.get(fname, 0.0),
                "cost_reason": MODULE_COST_FACTORS.get(fname, "Lógica padrão do módulo"),
                "functions": funcs,
                "is_single_bottleneck": is_single_bottleneck,
                "dominant_feature": dominant_func["name"] if is_single_bottleneck else None
            })

        aggregated_mods.sort(key=lambda x: x["mean_ms"], reverse=True)
        for item in aggregated_mods:
            item["percent"] = (item["mean_ms"] / max(total_avg_time, 0.001)) * 100

        return {
            "runs": runs,
            "total_avg_ms": total_avg_time,
            "modules": aggregated_mods
        }
