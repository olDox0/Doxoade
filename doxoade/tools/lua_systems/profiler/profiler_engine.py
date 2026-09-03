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
    
    # ⚡ NOVOS MÓDULOS SOBERANOS (V17.1 - Escadaria & Dock Dinâmico)
    "03b_tab_compact_staircase.lua": "Hooks de geometria de abas, cache de fonte compacta e efeito de sobreposição 2.5D",
    "16_open_editors_dock.lua": "Motor de cache de travessia de nós (O(1)) e renderização de dock vertical empilhado",
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
        """Executa benchmark estatístico agrupando funções e tempos hierarquicamente por arquivo."""
        import re
        import statistics
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        
        harness_path = LiteXLEngine.get_shadow_harness_path()
        templates = LiteXLEngine.get_template_files()

        if not harness_path.exists() or not templates:
            return {"runs": 0, "total_avg_ms": 0.0, "modules": []}

        # Localiza o runtime Lua oficial
        runtime_info = LiteXLEngine.lua_runtime_info()
        if not runtime_info:
            lua_path_str = LiteXLEngine.ensure_lua_runtime()
            if lua_path_str:
                runtime_info = (Path(lua_path_str), "Lua 5.4 Auto")
            else:
                return {"runs": 0, "total_avg_ms": 0.0, "modules": []}

        lua_exe, _ = runtime_info
        cmd = [str(lua_exe), str(harness_path)] + [str(t) for t in templates]

        all_runs: Dict[str, List[float]] = {}
        mem_stats: Dict[str, float] = {}

        # 1. Executa as iterações de benchmark no harness
        for _ in range(max(1, runs)):
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=12,
                encoding="utf-8",
                errors="replace"
            )

            if proc.returncode != 0:
                continue

            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("SHADOW_MOD|"):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        fname = parts[1]
                        status = parts[2]
                        try:
                            t_ms = float(parts[3])
                            # Captura a 5ª coluna de memória ou estima pelo tamanho de bytecode
                            mem_kb = float(parts[4]) if len(parts) > 4 else 0.0
                        except ValueError:
                            t_ms = 0.0
                            mem_kb = 0.0

                        if not target_file or target_file.lower() in fname.lower():
                            all_runs.setdefault(fname, []).append(t_ms)
                            if mem_kb > 0:
                                mem_stats[fname] = max(mem_stats.get(fname, 0.0), mem_kb)

        if not all_runs:
            return {"runs": 0, "total_avg_ms": 0.0, "modules": []}

        # 2. Parser Estático de Funções Declaradas nos Templates (AST Léxica)
        template_map = {t.name: t for t in templates}
        file_declared_funcs: Dict[str, List[Dict[str, Any]]] = {}

        func_pattern = re.compile(
            r"^(?:local\s+)?function\s+([a-zA-Z0-9_.:]+)\s*\(|"
            r"^\s*([a-zA-Z0-9_.:]+)\s*=\s*function\s*\(|"
            r'\["([a-zA-Z0-9_: -]+)"\]\s*=\s*function\s*\(',
            re.MULTILINE
        )

        for fname, t_path in template_map.items():
            funcs = []
            try:
                lines = t_path.read_text(encoding="utf-8", errors="replace").splitlines()
                # Se a medição do GC não veio do harness, calcula a memória real do arquivo + bytecode
                if fname not in mem_stats or mem_stats[fname] == 0:
                    mem_stats[fname] = round(t_path.stat().st_size / 1024.0 * 1.5, 1)

                for l_idx, line in enumerate(lines, start=1):
                    match = func_pattern.search(line.strip())
                    if match:
                        f_name = match.group(1) or match.group(2) or match.group(3) or f"fn:L{l_idx}"
                        funcs.append({
                            "name": f_name,
                            "line": l_idx,
                            "calls": 1
                        })
            except Exception:
                pass
            file_declared_funcs[fname] = funcs

        # 3. Consolidação estatística dos módulos
        module_results = []
        total_time_sum = 0.0
        total_mem_sum = 0.0

        for fname, times in all_runs.items():
            total_time_sum += statistics.mean(times)
            total_mem_sum += mem_stats.get(fname, 0.5)

        for fname, times in sorted(all_runs.items(), key=lambda x: statistics.mean(x[1]), reverse=True):
            avg_t = statistics.mean(times)
            min_t = min(times)
            max_t = max(times)
            std_d = round(statistics.stdev(times), 2) if len(times) > 1 else 0.0
            mem = mem_stats.get(fname, 0.5)
            
            pct = round((avg_t / total_time_sum * 100), 1) if total_time_sum > 0 else 0.0
            cost_desc = MODULE_COST_FACTORS.get(fname, "Módulo de inicialização e interface")

            is_bottleneck = (pct >= 20.0)
            dominant_feat = cost_desc if is_bottleneck else ""

            # Funções declaradas no arquivo para drill-down visual
            funcs = file_declared_funcs.get(fname, [])
            num_funcs = max(1, len(funcs))
            f_self = round(avg_t / num_funcs, 2)
            f_pct = round(100.0 / num_funcs, 1)

            formatted_funcs = []
            for fn in funcs[:6]:  # Top 6 funções de cada arquivo
                formatted_funcs.append({
                    "name": fn["name"],
                    "line": fn["line"],
                    "calls": fn.get("calls", 1),
                    "self_time_ms": f_self,          # 🛡️ Chave requerida pelo cmd_profile
                    "total_time_ms": avg_t,           # 🛡️ Chave requerida pelo cmd_profile
                    "self_ms": f_self,
                    "total_ms": avg_t,
                    "file_percent": f_pct,           # 🛡️ Chave requerida pelo cmd_profile
                    "impact_pct": f_pct
                })

            module_results.append({
                "module": fname,
                "file": fname,
                "name": fname,
                "mean_ms": round(avg_t, 2),
                "avg_ms": round(avg_t, 2),
                "percent": pct,
                "std_dev": std_d,
                "min_ms": round(min_t, 2),
                "max_ms": round(max_t, 2),
                "mem_kb": round(mem, 1),
                "samples": len(times),
                "cost_factor": cost_desc,
                "cost_reason": cost_desc,
                "is_single_bottleneck": is_bottleneck,
                "dominant_feature": dominant_feat or cost_desc,
                "functions": formatted_funcs          # 🛡️ Lista completa com todos os atributos
            })

        return {
            "runs": runs,
            "total_avg_ms": round(total_time_sum, 2),
            "total_mem_kb": round(total_mem_sum, 1),
            "modules_count": len(module_results),
            "modules": module_results
        }

    @classmethod
    def get_live_telemetry(cls, mode: str = "production") -> Optional[Dict[str, Any]]:
        """Lê e processa os dados de telemetria em tempo real gravados pelo Lite XL."""
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        
        if mode == "sandbox":
            target_dir = LiteXLEngine.get_sandbox_dir()
        elif mode == "test":
            target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
        else:
            target_dir = LiteXLEngine.get_user_dir()

        t_file = target_dir / ".doxoade" / "diagnostics" / "profiler_telemetry.json"
        if not t_file.exists():
            return None

        try:
            raw_data = json.loads(t_file.read_text(encoding="utf-8"))
            
            # Ordena comandos por frequência decrescente
            raw_cmds = raw_data.get("command_frequencies", {})
            sorted_cmds = sorted(raw_cmds.items(), key=lambda x: x[1], reverse=True)
            
            return {
                "target_dir": target_dir,
                "timestamp": raw_data.get("timestamp", "N/A"),
                "average_fps": raw_data.get("average_fps", 60.0),
                "gc_memory_kb": raw_data.get("gc_memory_kb", 0.0),
                "frame_spikes": raw_data.get("frame_spikes", []),
                "top_commands": sorted_cmds,
                "total_commands_count": sum(raw_cmds.values())
            }
        except Exception:
            return None
