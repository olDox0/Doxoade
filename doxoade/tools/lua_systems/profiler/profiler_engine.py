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

def resolve_thread_origin(thread_id: str, mode: str = "test") -> Tuple[str, Optional[Path], int]:
    """Mapeia 'init.lua:L8875' de volta para o template .lua original via Source Map."""
    m = re.match(r"(.*?):L?(\d+)", thread_id)
    if not m:
        return thread_id, None, 0

    raw_file, raw_line = m.group(1), int(m.group(2))
    
    # Se for um arquivo nativo ou template direto
    if raw_file.endswith(".lua") and not raw_file.endswith("init.lua"):
        # Tenta localizar na pasta de templates
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        t_path = LiteXLPaths.get_template_dir() / raw_file
        if t_path.exists():
            return raw_file, t_path, raw_line

    # Se for init.lua, resolve via Source Map unificado
    if "init.lua" in raw_file:
        try:
            from doxoade.commands.lite_xl_systems.typhon_doxly.doxly_khonsu_gate import DoxlyKhonsuGate
            target_path, rel_line, t_name = DoxlyKhonsuGate.resolve_unified_trace(raw_file, raw_line)
            if target_path and target_path.exists():
                return t_name, target_path, rel_line
        except Exception:
            pass

    return raw_file, None, raw_line

# =============================================================================
# 🧠 CHRONOS ADVISOR — MOTOR DE TOMADA DE DECISÃO BASEADA EM EVIDÊNCIAS
# =============================================================================
class ChronosAdvisor:
    """Analisa telemetria real e emite diagnósticos prescritivos automatizados."""

    @classmethod
    def generate_prescriptions(
        cls,
        live_data: Optional[Dict[str, Any]],
        boot_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        prescriptions: List[Dict[str, str]] = []

        # 1. Análise da Taxa de Quadros e Latência de Frame
        if live_data:
            fps = live_data.get("active_fps", 60.0)
            latency = live_data.get("avg_draw_latency_ms", 0.0)
            subs = live_data.get("subsystems", {})

            if latency > 16.67:
                # Localiza o maior vilão gráfico
                highest_sub = "Desconhecido"
                highest_val = 0.0
                sub_names = {
                    "doc_body_avg_ms": "Corpo do Código (Doc)",
                    "tabs_avg_ms": "Abas de Arquivo (Tabs)",
                    "gutter_avg_ms": "Marcadores do Gutter",
                    "rencache_avg_ms": "GPU / Rencache Flush",
                }
                for k, label in sub_names.items():
                    val = subs.get(k, 0.0)
                    if val > highest_val:
                        highest_val = val
                        highest_sub = label

                prescriptions.append({
                    "topic": "Latência de Frame Acima do Orçamento (Alerta 60 FPS)",
                    "evidence": f"Latência média de {latency:.2f}ms ({fps:.1f} FPS). O maior consumidor gráfico é '{highest_sub}' com {highest_val:.2f}ms.",
                    "diagnosis": f"A renderização gráfica está estourando a janela de 16.6ms devido à carga em {highest_sub}.",
                    "prescription": f"Aplicar memoization O(1) ou fatiamento de renderização em {highest_sub}."
                })
            else:
                prescriptions.append({
                    "topic": "Estabilidade de Frame Excelente",
                    "evidence": f"Latência de {latency:.2f}ms mantendo {fps:.1f} FPS estáveis.",
                    "diagnosis": "O pipeline de renderização opera dentro do orçamento ideal de 60 FPS.",
                    "prescription": "Nenhuma intervenção necessária no loop gráfico."
                })

            # 2. Análise de Corrotinas e Loops Contínuos
            threads = live_data.get("active_threads", {})
            for tid, st in threads.items():
                calls = st.get("calls", 0)
                cpu_ms = st.get("total_ms", 0.0)
                max_ms = st.get("max_ms", 0.0)

                # Flag de polling excessivo
                if calls > 300:
                    prescriptions.append({
                        "topic": f"Polling Contínuo Detectado: {tid}",
                        "evidence": f"A thread registrou {calls} ativações acumulando {cpu_ms:.2f}ms de CPU ativa.",
                        "diagnosis": "Loop em segundo plano acordando em taxa muito alta mesmo sem eventos pendentes.",
                        "prescription": "Substituir polling cego por Sono Reativo (yield maior quando fila/tabela estiver vazia)."
                    })

                # Flag de fatia bloqueante
                if max_ms > 15.0:
                    prescriptions.append({
                        "topic": f"Fatia Bloqueante de Thread: {tid}",
                        "evidence": f"A corrotina teve um pico ininterrupto de {max_ms:.2f}ms de CPU em uma única ativação.",
                        "diagnosis": "Operação monolítica sem fatiamento temporal (Khonsu Time-Slicing).",
                        "prescription": "Inserir coroutine.yield() em loops internos para não travar a renderização."
                    })

            # 3. Análise do Heap e Garbage Collector
            gc_rate = live_data.get("gc_growth_rate_kbs", 0.0)
            gc_ram = live_data.get("gc_memory_kb", 0.0) / 1024.0

            if gc_rate > 100.0:
                prescriptions.append({
                    "topic": "Pressão Alta no Garbage Collector",
                    "evidence": f"Taxa de alocação de {gc_rate:.1f} KB/s com heap em {gc_ram:.2f} MB.",
                    "diagnosis": "Criação contínua de tabelas ou strings descartáveis no ciclo de frame.",
                    "prescription": "Utilizar buffers estáticos reutilizáveis e evitar closures anônimas em funções chamadas por tick."
                })
            else:
                prescriptions.append({
                    "topic": "Alocação de Memória Estancada",
                    "evidence": f"Taxa de alocação estável em {gc_rate:.1f} KB/s com heap em {gc_ram:.2f} MB.",
                    "diagnosis": "O GC Generational do Lua 5.4 mantém o heap estável sem degradação.",
                    "prescription": "Regime de memória saudável aprovado."
                })

        # 4. Análise de Inicialização (Boot)
        if boot_data and boot_data.get("modules"):
            modules = boot_data["modules"]
            for m in modules:
                t_ms = m.get("time_ms", 0.0)
                if t_ms > 15.0:
                    prescriptions.append({
                        "topic": f"Carga Pesada no Boot: {m['name']}",
                        "evidence": f"O módulo consumiu {t_ms:.2f}ms e {m.get('mem_kb', 0):.1f} KB no carregamento inicial.",
                        "diagnosis": "Módulo com dependências pesadas sendo carregado no caminho crítico do boot.",
                        "prescription": f"Mover '{m['name']}' para DEFERRED_STAGE_TEMPLATES no Khonsu Gate (carregamento diferido)."
                    })

        return prescriptions

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
            fps = live_data.get("fps", live_data.get("active_fps", 60.0))
            cycle = live_data.get("cycle", {})
            percentiles = live_data.get("percentiles", {})
            p50 = percentiles.get("p50", 0.0)
            p95 = percentiles.get("p95", 0.0)
            p99 = percentiles.get("p99", 0.0)
            jitter = percentiles.get("jitter_ms", 0.0)

            step_logic_ms = cycle.get("step_logic_ms", 0.0)
            draw_ms = cycle.get("draw_ms", 0.0)
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
                    print(f"    ├─ Abas de Arquivo (Tabs) : {Fore.YELLOW}{subs.get('tabs_ms', subs.get('tabs_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Corpo do Código (Doc)  : {Fore.YELLOW}{subs.get('body_ms', subs.get('doc_body_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    ├─ Marcadores do Gutter   : {Fore.YELLOW}{subs.get('gutter_ms', subs.get('gutter_avg_ms', 0)):.2f}ms{Fore.RESET}")
                    print(f"    └─ GPU / Swap de Buffers  : {Fore.YELLOW}{subs.get('rencache_ms', subs.get('rencache_avg_ms', 0)):.2f}ms{Fore.RESET}\n")

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
