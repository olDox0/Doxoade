# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/profiler/profiler_engine.py
"""
⏱️ CHRONOS PROFILER & ADVISOR ENGINE — Diagnóstico Empírico de CPU, RAM e Prescrições.
Fase 1: Motor Chronos Advisor (Análise Baseada em Evidências), Watch Mode e Dossiê Markdown.
Compliance: ProDeNov 1.2.1, PASC-6.1, blitzplan_profile_2.md.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        GREEN = YELLOW = RED = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# =============================================================================
# 🧩 CHRONOS SNIPPET SOLVER (Apolo UX — Inspeção Automática de Código)
# =============================================================================
def get_source_snippet(file_path: Path, line_no: int, radius: int = 2) -> List[Tuple[int, bool, str]]:
    """Resgata as linhas ao redor do alvo para exibição forense."""
    if not file_path.exists():
        return []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, line_no - radius)
        end = min(len(lines), line_no + radius)
        snippet = []
        for ln in range(start, end + 1):
            snippet.append((ln, ln == line_no, lines[ln - 1]))
        return snippet
    except Exception:
        return []

def resolve_thread_origin(raw_id: str, mode: str = "test") -> Tuple[str, Optional[Path], int]:
    """Resolve o template e linha reais de uma thread inspecionando diretamente os banners do init.lua."""
    import re
    from pathlib import Path
    from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
    from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths

    m = re.match(r"^(.+?):L(\d+)$", raw_id)
    if not m:
        return raw_id, None, 0

    raw_file, raw_line = m.group(1), int(m.group(2))
    template_dir = LiteXLPaths.get_template_dir()
    if raw_file.startswith("core_kernel") or "core_kernel" in raw_id:
        return "⚡ Kernel Lite XL (Event Loop)", None, raw_line
    # 1. Se já for um arquivo .lua direto fora do init.lua
    if not raw_file.endswith("init.lua"):
        t_path = template_dir / raw_file
        if t_path.exists():
            return raw_file, t_path, raw_line
        return raw_file, None, raw_line

    # 2. Se for init.lua, resolve inspecionando o init.lua ativo na pasta de deploy
    try:
        user_dir = Path(LiteXLEngine.get_user_dir())
        target_init = (user_dir / ".doxoade" / "test_deploy" / "init.lua") if mode == "test" else (user_dir / "init.lua")

        if target_init.exists():
            lines = target_init.read_text(encoding="utf-8", errors="replace").splitlines()
            current_template = None
            template_start = 0

            for idx, line in enumerate(lines, start=1):
                m_start = re.match(r"--\s*>>>\s*\[TEMPLATE:\s*(.+?)\]\s*>>>", line)
                if m_start:
                    current_template = m_start.group(1).strip()
                    template_start = idx
                elif re.match(r"--\s*<<<\s*\[END\s+TEMPLATE:\s*(.+?)\]\s*<<<", line):
                    if idx >= raw_line and current_template:
                        break

                if idx == raw_line and current_template:
                    rel_line = max(1, raw_line - template_start)
                    t_path = template_dir / current_template
                    return current_template, (t_path if t_path.exists() else None), rel_line

            # Se a linha for anterior a qualquer template, pertence ao header
            if raw_line < 50:
                h_path = template_dir / "00_header_and_logger.lua"
                return "00_header_and_logger.lua", (h_path if h_path.exists() else None), raw_line
    except Exception:
        pass

    return raw_file, None, raw_line

# =============================================================================
# 🧠 CHRONOS ADVISOR — MOTOR DE TOMADA DE DECISÃO BASEADA EM EVIDÊNCIAS
# =============================================================================
class ChronosAdvisor:
    """Analisa telemetria real e emite diagnósticos prescritivos automatizados."""

    @classmethod
    def analyze(cls, live_data: dict, boot_data: dict) -> list[dict]:
        recommendations = []

        # 1. Extração das chaves reais do JSON do Lite XL
        percentiles = live_data.get("percentiles", {})
        p50 = float(percentiles.get("p50", 0.0))
        p95 = float(percentiles.get("p95", 0.0))
        p99 = float(percentiles.get("p99", 0.0))
        jitter = float(percentiles.get("jitter_ms", 0.0))

        fps = float(live_data.get("current_fps", live_data.get("fps", 0.0)))
        cycle = live_data.get("cycle", {})
        draw_ms = float(cycle.get("last_draw_ms", 0.0))
        logic_ms = float(cycle.get("step_logic_ms", 0.0))
        total_cycle_ms = float(cycle.get("step_total_ms", 0.0))

        gc_data = live_data.get("gc", {}) if isinstance(live_data.get("gc"), dict) else {}
        gc_kb = float(gc_data.get("memory_kb", live_data.get("gc_memory_kb", 0.0)))
        heap_mb = round(gc_kb / 1024.0, 2)
        alloc_rate = float(gc_data.get("growth_rate_kbs", live_data.get("gc_growth_rate_kbs", 0.0)))

        # gc_kb = float(live_data.get("gc_memory_kb", 0.0))
        # heap_mb = round(gc_kb / 1024.0, 2)
        # alloc_rate = float(live_data.get("gc_growth_rate_kbs", 0.0))

        # 2. Avaliação de Frame Rate e Latência Real
        if fps > 0.0 and (fps < 30.0 or p95 > 25.0):
            recommendations.append({
                "topic": f"Degradação Severa de Frame Rate ({fps:.1f} FPS)",
                "title": f"Degradação Severa de Frame Rate ({fps:.1f} FPS)",
                "evidence": f"P50: {p50:.2f}ms • P95: {p95:.2f}ms • Ciclo Total: {total_cycle_ms:.2f}ms.",
                "diagnosis": f"O editor está operando em taxa crítica ({fps:.1f} FPS). O loop está retido por corrotinas ou espera de eventos.",
                "prescription": "Inspecionar corrotinas no topo do ranking com ciclos ativos frequentes."
            })
        elif jitter > 10.0:
            recommendations.append({
                "topic": f"Jitter Elevado de Renderização ({jitter:.2f}ms)",
                "title": f"Jitter Elevado de Renderização ({jitter:.2f}ms)",
                "evidence": f"P50: {p50:.2f}ms saltando para P99: {p99:.2f}ms.",
                "diagnosis": "Picos esporádicos bloqueiam o redesenho suave.",
                "prescription": "Espaçar corrotinas em segundo plano e inspecionar threads com picos >5ms."
            })
        elif fps >= 55.0 and p95 <= 18.0:
            recommendations.append({
                "topic": "Estabilidade de Frame Excelente",
                "title": "Estabilidade de Frame Excelente",
                "evidence": f"Latência P95 em {p95:.2f}ms mantendo {fps:.1f} FPS estáveis.",
                "diagnosis": "O pipeline de renderização opera dentro do orçamento ideal de 60 FPS.",
                "prescription": "Nenhuma intervenção necessária no loop gráfico."
            })

        # 3. Avaliação de Lógica / IPC
        if logic_ms > 8.0:
            recommendations.append({
                "topic": f"Gargalo no Loop Lógico ({logic_ms:.2f}ms)",
                "title": f"Gargalo no Loop Lógico ({logic_ms:.2f}ms)",
                "evidence": f"core.step consumindo {logic_ms:.2f}ms por ciclo.",
                "diagnosis": "A fila de IPC ou corrotinas ativas estão retendo o frame.",
                "prescription": "Aplicar regime de Sono Reativo nas corrotinas do núcleo."
            })

        # 4. Avaliação de Memória Real
        if alloc_rate > 500.0:
            recommendations.append({
                "topic": f"Taxa de Alocação Elevada ({alloc_rate:.1f} KB/s)",
                "title": f"Taxa de Alocação Elevada ({alloc_rate:.1f} KB/s)",
                "evidence": f"Alocando {alloc_rate:.1f} KB/s com heap em {heap_mb:.2f} MB.",
                "diagnosis": "Criação contínua de strings ou tabelas temporárias em hotpaths.",
                "prescription": "Reutilizar tabelas (pooling) e evitar concatenações dentro de hooks contínuos."
            })
        else:
            recommendations.append({
                "topic": "Alocação de Memória Estancada",
                "title": "Alocação de Memória Estancada",
                "evidence": f"Taxa de alocação estável em {alloc_rate:.1f} KB/s com heap em {heap_mb:.2f} MB.",
                "diagnosis": "O GC Generational do Lua 5.4 mantém o heap estável sem degradação.",
                "prescription": "Regime de memória saudável aprovado."
            })

        # 5. Avaliação do Boot
        modules = boot_data.get("modules", []) if boot_data else []
        if modules:
            slowest = max(modules, key=lambda m: m.get("time_ms", 0.0))
            if slowest.get("time_ms", 0.0) >= 15.0:
                recommendations.append({
                    "topic": f"Carga Pesada no Boot: {slowest['name']}",
                    "title": f"Carga Pesada no Boot: {slowest['name']}",
                    "evidence": f"O módulo consumiu {slowest['time_ms']:.2f}ms e {slowest.get('mem_kb', 0.0):.1f} KB no boot.",
                    "diagnosis": "Módulo com dependências pesadas carregado no caminho crítico do boot.",
                    "prescription": f"Mover '{slowest['name']}' para DEFERRED_STAGE_TEMPLATES no Khonsu Gate (carregamento diferido)."
                })

        return recommendations

    @classmethod
    def generate_prescriptions(
        cls,
        live_data: Optional[Dict[str, Any]],
        boot_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Delega diretamente para o analyze, unificando a leitura de memória e latência."""
        return cls.analyze(live_data or {}, boot_data or {})
    # @classmethod
    # def generate_prescriptions(
    #     cls,
    #     live_data: Optional[Dict[str, Any]],
    #     boot_data: Optional[Dict[str, Any]]
    # ) -> List[Dict[str, str]]:
    #     prescriptions: List[Dict[str, str]] = []
    #     if not live_data:
    #         return prescriptions

    #     # 1. Extração das chaves reais do JSON gerado pelo 10_forensic_engine.lua
    #     percentiles = live_data.get("percentiles", {})
    #     p50 = float(percentiles.get("p50", 0.0))
    #     p95 = float(percentiles.get("p95", 0.0))
    #     p99 = float(percentiles.get("p99", 0.0))
    #     jitter = float(percentiles.get("jitter_ms", 0.0))

    #     fps = float(live_data.get("current_fps", live_data.get("active_fps", live_data.get("fps", 0.0))))
    #     cycle = live_data.get("cycle", {})
    #     draw_ms = float(cycle.get("last_draw_ms", 0.0))
    #     logic_ms = float(cycle.get("step_logic_ms", 0.0))
    #     total_cycle_ms = float(cycle.get("step_total_ms", 0.0))

    #     gc_kb = float(live_data.get("gc_memory_kb", 0.0))
    #     heap_mb = round(gc_kb / 1024.0, 2)
    #     alloc_rate = float(live_data.get("gc_growth_rate_kbs", 0.0))

    #     # 2. Avaliação de Frame Rate e Latência Real
    #     if fps > 0.0 and (fps < 30.0 or p95 > 25.0):
    #         prescriptions.append({
    #             "topic": f"Degradação Severa de Frame Rate ({fps:.1f} FPS)",
    #             "evidence": f"P50: {p50:.2f}ms • P95: {p95:.2f}ms • Ciclo Total: {total_cycle_ms:.2f}ms.",
    #             "diagnosis": f"O editor está operando em taxa crítica ({fps:.1f} FPS). O loop está retido por espera de eventos ou corrotinas.",
    #             "prescription": "Inspecionar corrotinas no topo do ranking (00_02_api_guard, autoreload, ipc_dispatcher)."
    #         })
    #     elif jitter > 10.0:
    #         prescriptions.append({
    #             "topic": f"Jitter Elevado de Renderização ({jitter:.2f}ms)",
    #             "evidence": f"P50: {p50:.2f}ms saltando para P99: {p99:.2f}ms.",
    #             "diagnosis": "Picos esporádicos bloqueiam o redesenho suave.",
    #             "prescription": "Espaçar corrotinas em segundo plano e inspecionar threads com picos >5ms."
    #         })
    #     elif fps >= 55.0 and p95 <= 18.0:
    #         prescriptions.append({
    #             "topic": "Estabilidade de Frame Excelente",
    #             "evidence": f"Latência P95 em {p95:.2f}ms mantendo {fps:.1f} FPS estáveis.",
    #             "diagnosis": "O pipeline de renderização opera dentro do orçamento ideal de 60 FPS.",
    #             "prescription": "Nenhuma intervenção necessária no loop gráfico."
    #         })

    #     # 3. Avaliação de Lógica / IPC
    #     if logic_ms > 8.0:
    #         prescriptions.append({
    #             "topic": f"Gargalo no Loop Lógico ({logic_ms:.2f}ms)",
    #             "evidence": f"core.step consumindo {logic_ms:.2f}ms por ciclo.",
    #             "diagnosis": "A fila de IPC ou corrotinas ativas estão retendo o frame.",
    #             "prescription": "Aplicar regime de Sono Reativo nas corrotinas do núcleo."
    #         })

    #     # 4. Avaliação de Memória Real
    #     if alloc_rate > 500.0:
    #         prescriptions.append({
    #             "topic": f"Taxa de Alocação Elevada ({alloc_rate:.1f} KB/s)",
    #             "evidence": f"Alocando {alloc_rate:.1f} KB/s com heap em {heap_mb:.2f} MB.",
    #             "diagnosis": "Criação contínua de strings ou tabelas temporárias em hotpaths.",
    #             "prescription": "Reutilizar tabelas (pooling) e evitar concatenações dentro de hooks contínuos."
    #         })
    #     else:
    #         prescriptions.append({
    #             "topic": "Alocação de Memória Estancada",
    #             "evidence": f"Taxa de alocação estável em {alloc_rate:.1f} KB/s com heap em {heap_mb:.2f} MB.",
    #             "diagnosis": "O GC Generational do Lua 5.4 mantém o heap estável sem degradação.",
    #             "prescription": "Regime de memória saudável aprovado."
    #         })

    #     # 5. Avaliação do Boot (se fornecido)
    #     if boot_data and isinstance(boot_data, dict):
    #         modules = boot_data.get("modules", [])
    #         if modules:
    #             slowest = max(modules, key=lambda m: m.get("time_ms", 0.0))
    #             if slowest.get("time_ms", 0.0) >= 15.0:
    #                 prescriptions.append({
    #                     "topic": f"Carga Pesada no Boot: {slowest['name']}",
    #                     "evidence": f"O módulo consumiu {slowest['time_ms']:.2f}ms e {slowest.get('mem_kb', 0.0):.1f} KB no carregamento inicial.",
    #                     "diagnosis": "Módulo com dependências pesadas carregado no caminho crítico do boot.",
    #                     "prescription": f"Mover '{slowest['name']}' para DEFERRED_STAGE_TEMPLATES no Khonsu Gate (carregamento diferido)."
    #                 })

    #     return prescriptions

    # # Alias para retrocompatibilidade
    # analyze = generate_prescriptions

# =============================================================================
# 📈 MOTORES MATEMÁTICOS DE SÉRIE TEMPORAL E SPARKLINES (CHRONOS V3)
# =============================================================================
def make_sparkline(values: list, width: int = 40) -> str:
    """Gera uma sparkline ASCII ( ▂▃▄▅▆▇█) a partir de uma lista de números."""
    if not values:
        return "N/A"
    chars = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    sample = values[-width:]
    min_v, max_v = min(sample), max(sample)
    if min_v == max_v:
        return chars[3] * len(sample)
    rng = max_v - min_v
    res = []
    for v in sample:
        idx = int(((v - min_v) / rng) * (len(chars) - 1))
        idx = max(0, min(len(chars) - 1, idx))
        res.append(chars[idx])
    return "".join(res)


def analyze_memory_drift(timeseries: list) -> tuple:
    """Calcula a inclinação linear de alocação de memória (KB/minuto)."""
    if len(timeseries) < 5:
        return 0.0, "ESTÁVEL (Amostras insuficientes)"

    window = timeseries[-60:]
    n = len(window)
    times = [i for i in range(n)]
    heaps = [s.get("gc_kb", 0.0) for s in window]

    # Regressão linear: slope = Cov(t, y) / Var(t)
    mean_t = sum(times) / n
    mean_h = sum(heaps) / n
    num = sum((times[i] - mean_t) * (heaps[i] - mean_h) for i in range(n))
    den = sum((times[i] - mean_t) ** 2 for i in range(n))

    slope_per_sec = (num / den) if den != 0 else 0.0
    drift_kb_min = slope_per_sec * 60.0

    if drift_kb_min > 500.0:
        verdict = f"CRÍTICO: Vazamento severo (+{drift_kb_min:.1f} KB/min)"
    elif drift_kb_min > 50.0:
        verdict = f"ALERTA: Deriva positiva detectada (+{drift_kb_min:.1f} KB/min)"
    elif drift_kb_min < -50.0:
        verdict = f"RECUPERAÇÃO: GC expurgando heap ({drift_kb_min:.1f} KB/min)"
    else:
        verdict = "SAUDÁVEL: Heap equilibrado sem deriva"

    return round(drift_kb_min, 1), verdict

# =============================================================================
# ⚙️ MOTOR PRINCIPAL DO PROFILER
# =============================================================================
class ProfilerEngine:
    """Analisador de Telemetria e Hotspots do Lite XL."""

    @staticmethod
    def get_telemetry_file(user_dir: Optional[Path] = None) -> Path:
        if user_dir is None:
            user_dir = Path.home() / ".config" / "lite-xl"
        return user_dir / ".doxoade" / "diagnostics" / "profiler_telemetry.json"

    @staticmethod
    def get_boot_telemetry_file(user_dir: Optional[Path] = None) -> Path:
        if user_dir is None:
            user_dir = Path.home() / ".config" / "lite-xl"
        return user_dir / ".doxoade" / "diagnostics" / "boot_telemetry.json"

    @staticmethod
    def get_dossier_file(user_dir: Optional[Path] = None) -> Path:
        if user_dir is None:
            user_dir = Path.home() / ".config" / "lite-xl"
        return user_dir / ".doxoade" / "diagnostics" / "profiler_dossier.md"

    @classmethod
    def load_report(cls, user_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        return cls.get_live_telemetry(mode="test" if user_dir and "test" in str(user_dir) else "production")

    @classmethod
    def load_boot_report(cls, user_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        b_file = cls.get_boot_telemetry_file(user_dir)
        if not b_file.exists():
            return None
        try:
            return json.loads(b_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None

    @classmethod
    def run_deep_benchmark(cls, runs: int = 5, target_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Benchmark empírico com dados reais de boot e runtime.
        Mantido para compatibilidade total de contrato com chamadas legadas de CLI e CI.
        """
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
        boot_data = cls.load_boot_report(target_dir) or cls.load_boot_report()
        live_data = cls.get_live_telemetry(mode="test") or cls.get_live_telemetry(mode="production")

        modules = (boot_data or {}).get("modules", [])
        return {
            "runs": runs,
            "total_avg_ms": (boot_data or {}).get("total_boot_ms", 0.0),
            "total_mem_kb": (boot_data or {}).get("total_boot_kb", 0.0),
            "modules_count": len(modules),
            "modules": modules,
            "live_data": live_data
        }

    @classmethod
    def get_live_telemetry(cls, mode: str = "production") -> Optional[Dict[str, Any]]:
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        if mode == "sandbox":
            target_dir = LiteXLEngine.get_sandbox_dir()
        elif mode == "test":
            target_dir = LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy"
        else:
            target_dir = LiteXLEngine.get_user_dir()

        t_file = cls.get_telemetry_file(target_dir)
        if not t_file.exists():
            return None
        try:
            return json.loads(t_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None

    @classmethod
    def export_markdown_dossier(
        cls,
        mode: str = "test",
        live_data: Optional[Dict[str, Any]] = None,
        boot_data: Optional[Dict[str, Any]] = None,
        prescriptions: Optional[List[Dict[str, str]]] = None
    ) -> Path:
        """Gera dossiê forense completo em Markdown para inspeção e arquivo."""
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        target_dir = (LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy") if mode == "test" else LiteXLEngine.get_user_dir()
        dossier_path = cls.get_dossier_file(target_dir)
        dossier_path.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = [
            f"# ⏱️ CHRONOS PROFILER DOSSIER — MODO [{mode.upper()}]",
            f"*Gerado em: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "## 1. Métricas de Runtime (Frame & Memória)",
        ]

        if live_data:
            fps = live_data.get("active_fps", 60.0)
            latency = live_data.get("avg_draw_latency_ms", 0.0)
            ram = live_data.get("gc_memory_kb", 0.0) / 1024.0
            rate = live_data.get("gc_growth_rate_kbs", 0.0)

            lines.extend([
                f"- **Taxa de Quadros:** `{fps:.1f} FPS`",
                f"- **Latência de Frame:** `{latency:.2f} ms`",
                f"- **Memória Alocada (GC):** `{ram:.2f} MB`",
                f"- **Taxa de Alocação de Heap:** `{rate:.1f} KB/s`\n",
                "### Custo por Subsistema Gráfico (Frame)",
                "| Subsistema | Custo Médio (ms) |",
                "| :--- | :--- |",
            ])

            subs = live_data.get("subsystems", {})
            lines.append(f"| Abas de Arquivo (Tabs) | {subs.get('tabs_avg_ms', 0):.2f} ms |")
            lines.append(f"| Corpo do Código (Doc) | {subs.get('doc_body_avg_ms', 0):.2f} ms |")
            lines.append(f"| Marcadores do Gutter | {subs.get('gutter_avg_ms', 0):.2f} ms |")
            lines.append(f"| GPU / Swap de Buffers | {subs.get('rencache_avg_ms', 0):.2f} ms |\n")

            threads = live_data.get("active_threads", {})
            if threads:
                lines.extend([
                    "### Corrotinas / Threads Ativas (Consumo de CPU)",
                    "| Thread / Módulo | CPU Total (ms) | Chamadas | Pico (ms) |",
                    "| :--- | :--- | :--- | :--- |",
                ])
                sorted_th = sorted(threads.items(), key=lambda x: x[1].get("total_ms", 0), reverse=True)
                for tid, st in sorted_th:
                    lines.append(f"| `{tid}` | {st.get('total_ms', 0):.2f} ms | {st.get('calls', 0)} | {st.get('max_ms', 0):.2f} ms |")
                lines.append("")
        else:
            lines.append("*Telemetria de runtime pendente.*\n")

        lines.append("## 2. Ranking Real de Inicialização (Boot Telemetry)")
        if boot_data and boot_data.get("modules"):
            lines.extend([
                f"- **Tempo Total no Boot:** `{boot_data.get('total_boot_ms', 0):.2f} ms`",
                f"- **RAM Total Alocada:** `{boot_data.get('total_boot_kb', 0):.1f} KB`\n",
                "| Módulo Template | Tempo (ms) | RAM (KB) | Status |",
                "| :--- | :--- | :--- | :--- |",
            ])
            sorted_mods = sorted(boot_data["modules"], key=lambda x: x.get("time_ms", 0), reverse=True)
            for m in sorted_mods:
                lines.append(f"| `{m['name']}` | {m.get('time_ms', 0):.2f} ms | {m.get('mem_kb', 0):.1f} KB | **{m.get('status', 'PASS')}** |")
            lines.append("")

        lines.append("## 3. 💡 Chronos Advisor — Tomada de Decisão Baseada em Evidências\n")
        if prescriptions:
            for idx, p in enumerate(prescriptions, start=1):
                lines.extend([
                    f"### #{idx} [{p['topic']}]",
                    f"- **Evidência:** {p['evidence']}",
                    f"- **Diagnóstico:** {p['diagnosis']}",
                    f"- **Prescrição:** `{p['prescription']}`\n",
                ])
        else:
            lines.append("*Nenhuma anomalia detectada. Sistema em estado ótimo de operação.*\n")

        dossier_path.write_text("\n".join(lines), encoding="utf-8")
        return dossier_path

    @classmethod
    def render_cli_profile(
        cls,
        mode: str = "test",
        show_boot: bool = True,
        show_threads: bool = True,
        show_subsystems: bool = True,
        show_advisor: bool = True,
        export_dossier: bool = False,
        as_json: bool = False,
        timeline: bool = False,
    ) -> Optional[Path]:
        """Renderiza o relatório de alta fidelidade com Chronos Advisor e Série Temporal."""
        from pathlib import Path
        import sys
        import time
        import json
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

        if sys.platform == "win32":
            try:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        # 1. Resolução segura de caminhos com Path() explícito (evita erro 'str' / 'str')
        user_dir = Path(LiteXLEngine.get_user_dir())
        if mode == "test":
            target_dir = user_dir / ".doxoade" / "test_deploy"
        elif mode == "sandbox":
            target_dir = Path(LiteXLEngine.get_sandbox_dir())
        else:
            target_dir = user_dir

        # 2. Carregamento seguro dos dados forenses
        boot_data = cls.load_boot_report(target_dir) or {}
        live_data = cls.get_live_telemetry(mode=mode) or {}

        # Heurística de prescrições
        try:
            prescriptions = ChronosAdvisor.generate_prescriptions(live_data, boot_data)
        except NameError:
            try:
                prescriptions = generate_prescriptions(live_data, boot_data)
            except Exception:
                prescriptions = []
        except Exception:
            prescriptions = []

        if as_json:
            payload = {
                "mode": mode,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "live_telemetry": live_data,
                "boot_telemetry": boot_data,
                "prescriptions": prescriptions,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return None

        # 3. Cabeçalho unificado Chronos V3
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"⏱️  CHRONOS PROFILER & ADVISOR — RELATÓRIO BASEADO EM EVIDÊNCIAS [{mode.upper()}]")
        print(f"{'═' * 75}{Style.RESET_ALL}\n")

        # 4. Métricas de ciclo, frame e percentis
        if live_data:
            percentiles = live_data.get("percentiles", {})
            p50 = float(percentiles.get("p50", 0.0))
            p95 = float(percentiles.get("p95", 0.0))
            p99 = float(percentiles.get("p99", 0.0))
            jitter = float(percentiles.get("jitter_ms", 0.0))

            fps = float(live_data.get("current_fps", live_data.get("fps", 0.0)))
            cycle = live_data.get("cycle", {})
            # Fallback seguro: busca "draw_ms" ou "last_draw_ms"
            draw_ms = float(cycle.get("draw_ms") or cycle.get("last_draw_ms") or 0.0)
            logic_ms = float(cycle.get("step_logic_ms", 0.0))
            total_cycle_ms = float(cycle.get("step_total_ms", 0.0))

            gc_data = live_data.get("gc", {}) if isinstance(live_data.get("gc"), dict) else {}
            gc_kb = float(gc_data.get("memory_kb", live_data.get("gc_memory_kb", 0.0)))
            heap_mb = round(gc_kb / 1024.0, 2)
            alloc_rate = float(gc_data.get("growth_rate_kbs", live_data.get("gc_growth_rate_kbs", 0.0)))

            step_logic_ms = cycle.get("step_logic_ms", 0.0)
            #draw_ms = cycle.get("draw_ms", 0.0)
            step_total_ms = cycle.get("step_total_ms", 0.0)

            gc_mem_kb = live_data.get("gc", {}).get("memory_kb", live_data.get("gc_memory_kb", 0.0))
            gc_rate_kbs = live_data.get("gc", {}).get("growth_rate_kbs", live_data.get("gc_growth_rate_kbs", 0.0))

            fps_col = Fore.GREEN if fps >= 55 else (Fore.YELLOW if fps >= 30 else Fore.RED)
            print(f"  {Fore.WHITE}Taxa de Quadros:{Fore.RESET} {fps_col}{fps:.1f} FPS{Fore.RESET} "
                  f"| {Fore.WHITE}Latência:{Fore.RESET} P50: {p50:.2f}ms • P95: {p95:.2f}ms • P99: {p99:.2f}ms • Jitter: {jitter:.2f}ms")
            print(f"  {Fore.WHITE}Ciclo do Loop   :{Fore.RESET} Lógica/IPC: {Fore.CYAN}{step_logic_ms:.2f}ms{Fore.RESET} "
                  f"| Render/SDL2: {Fore.CYAN}{draw_ms:.2f}ms{Fore.RESET} | Total: {step_total_ms:.2f}ms")
            print(f"  {Fore.WHITE}Memória Lua (GC):{Fore.RESET} {gc_mem_kb / 1024.0:.2f} MB "
                  f"| {Fore.WHITE}Taxa de Alocação:{Fore.RESET} {gc_rate_kbs:.1f} KB/s\n")

            # 5. Custos dos Subsistemas Gráficos
            if show_subsystems:
                subs = live_data.get("subsystems", {})
                if subs:
                    print(f"  {Fore.MAGENTA}■ CUSTO REAL POR SUBSISTEMA GRÁFICO (Frame):{Fore.RESET}")
                    print(f"    ├─ Abas de Arquivo (Tabs)   : {Fore.YELLOW}{subs.get('tabs_ms', subs.get('tabs_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Corpo do Código (Doc)    : {Fore.YELLOW}{subs.get('body_ms', subs.get('doc_body_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Marcadores do Gutter     : {Fore.YELLOW}{subs.get('gutter_ms', subs.get('gutter_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Árvore de Pastas (Tree)  : {Fore.YELLOW}{subs.get('tree_ms', 0.0):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Barra de Status (HUD)    : {Fore.YELLOW}{subs.get('status_ms', 0.0):.2f}ms{Fore.RESET}")
                    print(f"    └─ GPU / Swap de Buffers    : {Fore.YELLOW}{subs.get('rencache_ms', subs.get('rencache_avg_ms', 0)):.2f}ms{Fore.RESET}\n")

            # 6. Threads e Corrotinas Ativas
            if show_threads:
                threads = live_data.get("threads", live_data.get("active_threads", []))
                if threads:
                    print(f"  {Fore.CYAN}■ CORROTINAS / THREADS ATIVAS (Consumo Acumulado):{Fore.RESET}")
                    if isinstance(threads, list):
                        sorted_th = sorted(threads, key=lambda x: x.get("cpu_ms", x.get("total_ms", 0)), reverse=True)
                        # Exibe o ranking de threads
                        top_culprit_thread = sorted_th[0] if sorted_th else None

                        for idx, st in enumerate(sorted_th[:6]):
                            tid = st.get("id", "thread")
                            total_ms = st.get("cpu_ms", st.get("total_ms", 0))
                            calls = st.get("calls", 0)
                            peak = st.get("peak_ms", st.get("max_ms", 0))
                            
                            # Resolve o nome real do template
                            t_name, t_path, rel_line = resolve_thread_origin(tid, mode=mode)
                            display_id = f"{t_name}:L{rel_line}" if t_path else tid

                            print(f"    • {Fore.WHITE}{display_id:<34}{Fore.RESET} "
                                f"CPU: {Fore.YELLOW}{total_ms:6.2f}ms{Fore.RESET} "
                                f"({calls:>3} calls | pico: {Fore.RED if peak > 15 else Fore.YELLOW}{peak:5.2f}ms{Fore.RESET})")

                        # 🧩 CHRONOS SNIPPET SOLVER: Imprime o código-fonte da thread número 1
                        if top_culprit_thread:
                            top_id = top_culprit_thread.get("id", "")
                            t_name, t_path, rel_line = resolve_thread_origin(top_id, mode=mode)
                            if t_path and t_path.exists() and rel_line > 0:
                                snippets = get_source_snippet(t_path, rel_line, radius=2)
                                if snippets:
                                    print(f"\n      {Fore.CYAN}┌─ [SNIPPET SOLVER] 📄 {t_name}:{rel_line}{Fore.RESET}")
                                    for ln, is_target, code in snippets:
                                        prefix = f"{Fore.RED} >> {Fore.RESET}" if is_target else "    "
                                        num_col = f"{Fore.YELLOW}{ln:4d} |{Fore.RESET}"
                                        print(f"      {prefix}{num_col} {code}")
                                    print(f"      {Fore.CYAN}└{'─' * 55}{Fore.RESET}\n")
                    elif isinstance(threads, dict):
                        sorted_th = sorted(threads.items(), key=lambda x: x[1].get("total_ms", 0), reverse=True)
                        for tid, st in sorted_th[:8]:
                            print(f"    • {Fore.WHITE}{tid:<32}{Fore.RESET} "
                                  f"CPU: {Fore.YELLOW}{st.get('total_ms', 0):.2f}ms{Fore.RESET} "
                                  f"({st.get('calls', 0)} calls | pico: {st.get('max_ms', 0):.2f}ms)")
                    print()
        else:
            print(f"  {Fore.YELLOW}⚠ Telemetria de runtime pendente (abra o editor para capturar).{Fore.RESET}\n")

        # 7. Série Temporal com Sparklines (exibe se houver dados ou flag timeline)
        timeseries = live_data.get("timeseries", [])
        if timeseries and (timeline or not (show_boot or show_threads)):
            fps_samples = [s.get("fps", 60.0) for s in timeseries]
            frame_samples = [s.get("frame_ms", 0.0) for s in timeseries]
            heap_samples = [s.get("gc_kb", 0.0) / 1024.0 for s in timeseries]

            drift_rate, drift_verdict = analyze_memory_drift(timeseries)
            drift_color = Fore.GREEN if "SAUDÁVEL" in drift_verdict else (Fore.YELLOW if "ALERTA" in drift_verdict else Fore.RED)

            print(f"  {Fore.CYAN}{Style.BRIGHT}📈 SÉRIE TEMPORAL E TENDÊNCIA ({len(timeseries)}s de histórico):{Style.RESET_ALL}")
            print(f"    ├─ FPS (últimos 40s)      : {Fore.GREEN}{make_sparkline(fps_samples, 40)}{Fore.RESET} ({fps_samples[-1]:.1f} FPS)")
            print(f"    ├─ Latência de Frame (ms) : {Fore.CYAN}{make_sparkline(frame_samples, 40)}{Fore.RESET} ({frame_samples[-1]:.2f}ms)")
            print(f"    ├─ Heap GC (MB)           : {Fore.MAGENTA}{make_sparkline(heap_samples, 40)}{Fore.RESET} ({heap_samples[-1]:.2f} MB)")
            print(f"    └─ Deriva de Memória      : {drift_color}{drift_verdict}{Fore.RESET}\n")

            print(f"  {Fore.WHITE}{Style.BRIGHT}⏱️  HISTÓRICO CRONOLÓGICO DOS ÚLTIMOS SEGUNDOS:{Style.RESET_ALL}")
            print(f"    {'SEGUNDO':<10} {'FPS':<6} {'P95 (ms)':<9} {'LÓGICA':<9} {'RENDER':<9} {'RAM (MB)':<10} {'MAIOR CONSUMIDOR':<25}")
            print(f"    {'─' * 82}")
            for s in timeseries[-6:]:
                t_str = time.strftime("%H:%M:%S", time.localtime(s.get("ts", time.time())))
                top_th = f"{s.get('top_thread', 'none')} ({s.get('top_cpu', 0.0):.1f}ms)"
                print(f"    {t_str:<10} {s.get('fps', 60.0):<6.1f} {s.get('p95', 0.0):<9.2f} "
                      f"{s.get('step_ms', 0.0):<9.2f} {s.get('draw_ms', 0.0):<9.2f} "
                      f"{s.get('gc_kb', 0.0) / 1024.0:<10.2f} {top_th[:25]:<25}")
            print()

        # 8. Ranking de Inicialização (Boot Telemetry)
        if show_boot and boot_data and boot_data.get("modules"):
            modules = boot_data["modules"]
            sorted_mods = sorted(modules, key=lambda x: x.get("time_ms", 0), reverse=True)

            print(f"  {Fore.GREEN}■ RANKING REAL DE INICIALIZAÇÃO (Boot Telemetry):{Fore.RESET}")
            print(f"  {Fore.LIGHTBLACK_EX}Total no Boot: {boot_data.get('total_boot_ms', 0):.2f}ms | "
                  f"RAM Alocada: {boot_data.get('total_boot_kb', 0):.1f} KB{Fore.RESET}\n")

            print(f"    {Style.BRIGHT}{'MÓDULO':<38} {'TEMPO (ms)':<14} {'RAM (KB)':<12} {'STATUS'}{Style.RESET_ALL}")
            print(f"    {Fore.LIGHTBLACK_EX}{'─' * 70}{Fore.RESET}")

            for m in sorted_mods:
                t_ms = m.get("time_ms", 0)
                t_col = Fore.RED if t_ms > 20 else (Fore.YELLOW if t_ms > 5 else Fore.GREEN)
                stat_col = Fore.GREEN if m.get("status") == "PASS" else Fore.RED
                print(f"    {m['name']:<38} {t_col}{t_ms:>8.2f}ms{Fore.RESET}     "
                      f"{Fore.CYAN}{m.get('mem_kb', 0):>7.1f} KB{Fore.RESET}   "
                      f"{stat_col}{m.get('status', 'PASS')}{Fore.RESET}")
            print()

        # 9. Parecer Prescritivo do Chronos Advisor
        if show_advisor and prescriptions:
            print(f"{Fore.CYAN}{'═' * 75}")
            print(f"💡 CHRONOS ADVISOR — TOMADA DE DECISÃO BASEADA EM EVIDÊNCIAS")
            print(f"{'═' * 75}{Style.RESET_ALL}\n")

            for idx, p in enumerate(prescriptions, start=1):
                is_warn = "Alerta" in p["topic"] or "Detectado" in p["topic"] or "Bloqueante" in p["topic"]
                topic_col = Fore.YELLOW if is_warn else Fore.GREEN
                print(f"  {topic_col}▶ #{idx} [{p['topic']}]{Fore.RESET}")
                print(f"     {Fore.LIGHTBLACK_EX}├─ [EVIDÊNCIA]   :{Fore.RESET} {p['evidence']}")
                print(f"     {Fore.LIGHTBLACK_EX}├─ [DIAGNÓSTICO] :{Fore.RESET} {p['diagnosis']}")
                print(f"     {Fore.LIGHTBLACK_EX}└─ [PRESCRIÇÃO]  :{Fore.RESET} {Fore.CYAN}{p['prescription']}{Fore.RESET}\n")

        # 10. Exportação do Dossiê Markdown
        dossier_saved = None
        if export_dossier:
            dossier_saved = cls.export_markdown_dossier(
                mode=mode,
                live_data=live_data,
                boot_data=boot_data,
                prescriptions=prescriptions
            )
            print(f"  💾 {Fore.GREEN}Dossiê salvo com sucesso em:{Fore.RESET} {dossier_saved}\n")

        return dossier_saved

    @classmethod
    def run_watch_mode(cls, mode: str = "test", interval: float = 1.5) -> None:
        """Modo Sentinela contínuo (estilo htop)."""
        print(f"{Fore.CYAN}⏱️  Iniciando modo Watch do Chronos Profiler (Ctrl+C para sair)...{Fore.RESET}")
        try:
            while True:
                # Limpa a tela do console de forma suave
                if os.name == "nt":
                    os.system("cls")
                else:
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()

                cls.render_cli_profile(mode=mode, show_boot=False, show_advisor=True)
                print(f"  {Fore.LIGHTBLACK_EX}Próxima amostragem em {interval}s... (Ctrl+C para encerrar){Fore.RESET}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Modo Watch encerrado pelo usuário.{Fore.RESET}\n")
