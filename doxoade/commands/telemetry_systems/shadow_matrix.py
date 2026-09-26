# -*- coding: utf-8 -*-
# doxoade/commands/telemetry_systems/shadow_matrix.py
"""
🦅 HORUS / NSR — Shadow Timeline Matrix Engine v5.1.
Módulo de instrumentação temporal transparente para o Doxoade.
Combina amostragem multi-thread de 200Hz, ribbons CP437, métricas
de CPU normalizada, decomposição de memória RAM e throughput de disco.
"""
from __future__ import annotations

import sys
import os
import time
import json
import tracemalloc
import threading
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

MAX_PERSISTED_DUMPS = 20

class CompactSeriesEncoder(json.JSONEncoder):
    """Concatena vetores de séries temporais inline mantendo o resto indentado."""
    def encode(self, o):
        if isinstance(o, (list, tuple)):
            if o and all(isinstance(x, (int, float)) for x in o):
                return "[" + ", ".join(f"{x:.1f}" if isinstance(x, float) else str(x) for x in o) + "]"
        return super().encode(o)

def _generate_shaded_ribbon(values: List[float], width: int = 24) -> str:
    """Gera um ribbon temporal usando blocos de densidade padrão CP437 (░▒▓█)."""
    if not values:
        return "[dim]░[/dim]" * width

    if len(values) > width:
        chunk_size = len(values) / width
        resampled = []
        for i in range(width):
            start_idx = int(i * chunk_size)
            end_idx = max(start_idx + 1, int((i + 1) * chunk_size))
            sub = values[start_idx:end_idx]
            resampled.append(sum(sub) / len(sub) if sub else 0.0)
        values = resampled
    elif len(values) < width:
        values = [values[0]] * (width - len(values)) + values

    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val

    if val_range <= 0.0001:
        return "[dim green]░[/dim green]" * width

    result = []
    for v in values:
        norm = (v - min_val) / val_range
        if norm <= 0.25:
            result.append("[green]░[/green]")
        elif norm <= 0.55:
            result.append("[yellow]▒[/yellow]")
        elif norm <= 0.85:
            result.append("[bold red]▓[/bold red]")
        else:
            result.append("[bold white on red]█[/bold white on red]")

    return "".join(result)


def _render_composition_bar(boot_pct: float, heap_pct: float, native_pct: float, width: int = 40) -> str:
    """Gera uma barra proporcional colorida da distribuição de memória."""
    w_boot = int(round((boot_pct / 100.0) * width))
    w_heap = int(round((heap_pct / 100.0) * width))
    w_native = max(0, width - (w_boot + w_heap))

    return (
        f"[bold blue]{'█' * w_boot}[/bold blue]"
        f"[bold yellow]{'█' * w_heap}[/bold yellow]"
        f"[bold cyan]{'█' * w_native}[/bold cyan]"
    )


class ShadowMatrix:
    """Orquestrador do Shadow Profiling com inspeção temporal multi-thread e auto-prune."""

    def __init__(self, target_name: str, enabled: bool = True, sample_rate_hz: int = 200):
        self.target_name = target_name
        self.enabled = enabled
        self.interval = 1.0 / sample_rate_hz
        self.start_wall_time = 0.0
        self.elapsed_ms = 0.0
        self.num_cpus = os.cpu_count() or 1

        self.proc = psutil.Process() if HAS_PSUTIL else None
        self.boot_rss_mb = 0.0
        if self.proc:
            try:
                self.boot_rss_mb = round(self.proc.memory_info().rss / (1024 * 1024), 2)
            except Exception:
                pass

        # Séries temporais (ticks a cada ~5ms)
        self.timeline_ticks: List[float] = []
        self.timeline_proc_cpu: List[float] = []
        self.timeline_total_cpu: List[float] = []
        self.timeline_rss_ram: List[float] = []
        self.timeline_heap_ram: List[float] = []
        self.timeline_native_ram: List[float] = []
        self.timeline_read_speed_kbps: List[float] = []
        self.timeline_write_speed_kbps: List[float] = []
        self.timeline_locs: List[str] = []

        self._samples = defaultdict(int)
        self._stop_event = threading.Event()
        self._sampler_thread: Optional[threading.Thread] = None

        self.last_cputimes = None
        self.last_wall_tick = 0.0
        self.last_io_counters = None
        self.init_io_counters = None
        self.tracked_files: List[str] = []

        self.output_dir = Path.home() / ".doxoade" / "shadow_profiling"
        self.report_data: Dict[str, Any] = {}

    def _sampler_loop(self):
        """Loop de amostragem em 200Hz com varredura de todas as threads ativas."""
        t0 = self.start_wall_time

        while not self._stop_event.is_set():
            t_now = time.perf_counter()
            elapsed_ms = (t_now - t0) * 1000.0
            dt = t_now - self.last_wall_tick if self.last_wall_tick > 0 else self.interval
            self.last_wall_tick = t_now

            proc_cpu = 0.0
            total_cpu_pct = 0.0
            rss_val = self.boot_rss_mb
            heap_val = 0.0
            read_speed_kbps = 0.0
            write_speed_kbps = 0.0

            if self.proc:
                try:
                    ct = self.proc.cpu_times()
                    if self.last_cputimes and dt > 0:
                        u_delta = ct.user - self.last_cputimes.user
                        s_delta = ct.system - self.last_cputimes.system
                        proc_cpu = ((u_delta + s_delta) / dt) * 100.0
                        total_cpu_pct = proc_cpu / self.num_cpus
                    self.last_cputimes = ct

                    rss_val = self.proc.memory_info().rss / (1024 * 1024)

                    curr_io = self.proc.io_counters()
                    if self.last_io_counters and dt > 0:
                        r_bytes = max(0, curr_io.read_bytes - self.last_io_counters.read_bytes)
                        w_bytes = max(0, curr_io.write_bytes - self.last_io_counters.write_bytes)
                        read_speed_kbps = (r_bytes / 1024.0) / dt
                        write_speed_kbps = (w_bytes / 1024.0) / dt
                    self.last_io_counters = curr_io
                except Exception:
                    pass

            try:
                curr_traced, _ = tracemalloc.get_traced_memory()
                heap_val = curr_traced / (1024 * 1024)
            except Exception:
                heap_val = 0.0

            native_val = max(0.0, rss_val - (self.boot_rss_mb + heap_val))

            frames = sys._current_frames()
            active_locations = []
            
            # 🛑 SILENCIAMENTO DE RUÍDO DO OBSERVADOR:
            IGNORE_NOISE = {"chronos.py", "threading.py", "shadow_matrix.py", "aegis_core.py"}

            for tid, frame in frames.items():
                if self._sampler_thread and tid == self._sampler_thread.ident:
                    continue

                code = frame.f_code
                filename = code.co_filename.replace("\\", "/")

                # Ignora as threads de telemetria para registrar apenas o código de trabalho
                if any(noise in filename for noise in IGNORE_NOISE):
                    continue

                if "doxoade" in filename and "site-packages" not in filename:
                    rel_file = filename.split("doxoade/")[-1]
                    key = (rel_file, frame.f_lineno, code.co_name)
                    self._samples[key] += 1
                    active_locations.append(f"{rel_file}:{frame.f_lineno}")

            loc_summary = active_locations[0] if active_locations else "idle"

            self.timeline_ticks.append(round(elapsed_ms, 1))
            self.timeline_proc_cpu.append(round(proc_cpu, 1))
            self.timeline_total_cpu.append(round(total_cpu_pct, 1))
            self.timeline_rss_ram.append(round(rss_val, 2))
            self.timeline_heap_ram.append(round(heap_val, 2))
            self.timeline_native_ram.append(round(native_val, 2))
            self.timeline_read_speed_kbps.append(round(read_speed_kbps, 1))
            self.timeline_write_speed_kbps.append(round(write_speed_kbps, 1))
            self.timeline_locs.append(loc_summary)

            time.sleep(self.interval)

    def __enter__(self):
        if not self.enabled:
            return self

        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            tracemalloc.start()
        except Exception:
            pass

        if self.proc:
            try:
                self.boot_rss_mb = round(self.proc.memory_info().rss / (1024 * 1024), 2)
                self.last_cputimes = self.proc.cpu_times()
                self.init_io_counters = self.proc.io_counters()
                self.last_io_counters = self.init_io_counters
            except Exception:
                pass

        self.start_wall_time = time.perf_counter()
        self.last_wall_tick = self.start_wall_time
        self._stop_event.clear()
        self._sampler_thread = threading.Thread(target=self._sampler_loop, daemon=True)
        self._sampler_thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.enabled:
            return

        self._stop_event.set()
        if self._sampler_thread:
            self._sampler_thread.join(timeout=0.6)

        self.elapsed_ms = (time.perf_counter() - self.start_wall_time) * 1000.0

        try:
            tracemalloc.stop()
        except Exception:
            pass

        if self.proc:
            try:
                open_files = self.proc.open_files()
                self.tracked_files = [
                    f.path for f in open_files
                    if not f.path.endswith((".pyd", ".dll", ".so"))
                ][:8]
            except Exception:
                pass

        self._compile_full_matrix()
        self._persist_matrix()
        self._prune_old_dumps()

    def _compile_full_matrix(self):
        """Calcula agregados, distribuições e percentuais."""
        total_samples = sum(self._samples.values())
        hot_paths = []

        for (rel_file, lineno, func_name), hits in self._samples.items():
            pct = (hits / total_samples * 100.0) if total_samples > 0 else 0.0
            est_ms = (hits / total_samples) * self.elapsed_ms if total_samples > 0 else 0.0
            avg_per_hit_ms = est_ms / hits if hits > 0 else 0.0

            hot_paths.append({
                "file": rel_file,
                "line": lineno,
                "func": func_name,
                "hits": hits,
                "pct": round(pct, 1),
                "est_ms": round(est_ms, 2),
                "avg_ms": round(avg_per_hit_ms, 3)
            })

        hot_paths.sort(key=lambda x: x["hits"], reverse=True)

        peak_proc_cpu = max(self.timeline_proc_cpu) if self.timeline_proc_cpu else 0.0
        avg_proc_cpu = sum(self.timeline_proc_cpu) / len(self.timeline_proc_cpu) if self.timeline_proc_cpu else 0.0
        peak_total_cpu = max(self.timeline_total_cpu) if self.timeline_total_cpu else 0.0
        avg_total_cpu = sum(self.timeline_total_cpu) / len(self.timeline_total_cpu) if self.timeline_total_cpu else 0.0

        peak_rss = max(self.timeline_rss_ram) if self.timeline_rss_ram else self.boot_rss_mb
        avg_rss = sum(self.timeline_rss_ram) / len(self.timeline_rss_ram) if self.timeline_rss_ram else self.boot_rss_mb
        avg_heap = sum(self.timeline_heap_ram) / len(self.timeline_heap_ram) if self.timeline_heap_ram else 0.0
        peak_heap = max(self.timeline_heap_ram) if self.timeline_heap_ram else 0.0
        avg_native = sum(self.timeline_native_ram) / len(self.timeline_native_ram) if self.timeline_native_ram else 0.0

        total_comp = self.boot_rss_mb + avg_heap + avg_native
        pct_boot = (self.boot_rss_mb / total_comp) * 100.0 if total_comp > 0 else 100.0
        pct_heap = (avg_heap / total_comp) * 100.0 if total_comp > 0 else 0.0
        pct_native = (avg_native / total_comp) * 100.0 if total_comp > 0 else 0.0

        total_read_mb = 0.0
        total_write_mb = 0.0
        read_ops = 0
        write_ops = 0

        if self.proc and self.init_io_counters and self.last_io_counters:
            try:
                total_read_mb = (self.last_io_counters.read_bytes - self.init_io_counters.read_bytes) / (1024.0 * 1024.0)
                total_write_mb = (self.last_io_counters.write_bytes - self.init_io_counters.write_bytes) / (1024.0 * 1024.0)
                read_ops = self.last_io_counters.read_count - self.init_io_counters.read_count
                write_ops = self.last_io_counters.write_count - self.init_io_counters.write_count
            except Exception:
                pass

        peak_read_speed = max(self.timeline_read_speed_kbps) if self.timeline_read_speed_kbps else 0.0
        avg_read_speed = sum(self.timeline_read_speed_kbps) / len(self.timeline_read_speed_kbps) if self.timeline_read_speed_kbps else 0.0
        peak_write_speed = max(self.timeline_write_speed_kbps) if self.timeline_write_speed_kbps else 0.0
        avg_write_speed = sum(self.timeline_write_speed_kbps) / len(self.timeline_write_speed_kbps) if self.timeline_write_speed_kbps else 0.0

        chrono_phases = []
        if self.timeline_locs:
            step = max(1, len(self.timeline_locs) // 6)
            for i in range(0, len(self.timeline_locs), step):
                window = self.timeline_locs[i:i + step]
                dominant = max(set(window), key=window.count)
                t_start = self.timeline_ticks[i]
                t_end = self.timeline_ticks[min(i + step - 1, len(self.timeline_ticks) - 1)]
                chrono_phases.append({
                    "start_ms": t_start,
                    "end_ms": t_end,
                    "focus": dominant
                })

        self.report_data = {
            "target": self.target_name,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "wall_time_ms": round(self.elapsed_ms, 2),
            "hardware": {
                "num_cpus": self.num_cpus,
                "total_samples": total_samples,
                "sample_rate_hz": int(1.0 / self.interval)
            },
            "cpu": {
                "peak_proc_cpu": round(peak_proc_cpu, 1),
                "avg_proc_cpu": round(avg_proc_cpu, 1),
                "peak_total_cpu": round(peak_total_cpu, 1),
                "avg_total_cpu": round(avg_total_cpu, 1),
                "ribbon": _generate_shaded_ribbon(self.timeline_proc_cpu)
            },
            "memory": {
                "boot_base_mb": self.boot_rss_mb,
                "avg_rss_mb": round(avg_rss, 2),
                "peak_rss_mb": round(peak_rss, 2),
                "delta_mb": round(peak_rss - self.boot_rss_mb, 2),
                "avg_heap_mb": round(avg_heap, 2),
                "peak_heap_mb": round(peak_heap, 2),
                "avg_native_mb": round(avg_native, 2),
                "composition_pct": {
                    "boot": round(pct_boot, 1),
                    "heap": round(pct_heap, 1),
                    "native": round(pct_native, 1)
                },
                "ribbon_rss": _generate_shaded_ribbon(self.timeline_rss_ram),
                "ribbon_heap": _generate_shaded_ribbon(self.timeline_heap_ram)
            },
            "disk": {
                "total_read_mb": round(total_read_mb, 2),
                "total_write_mb": round(total_write_mb, 2),
                "read_ops": read_ops,
                "write_ops": write_ops,
                "peak_read_speed_kbps": round(peak_read_speed, 1),
                "avg_read_speed_kbps": round(avg_read_speed, 1),
                "peak_write_speed_kbps": round(peak_write_speed, 1),
                "avg_write_speed_kbps": round(avg_write_speed, 1),
                "ribbon_read_speed": _generate_shaded_ribbon(self.timeline_read_speed_kbps),
                "ribbon_write_speed": _generate_shaded_ribbon(self.timeline_write_speed_kbps),
                "active_files": self.tracked_files
            },
            "chrono_phases": chrono_phases,
            "hot_paths": hot_paths[:10],
            "series": {
                "ticks_ms": self.timeline_ticks,
                "proc_cpu_pct": self.timeline_proc_cpu,
                "total_cpu_pct": self.timeline_total_cpu,
                "rss_ram_mb": self.timeline_rss_ram,
                "heap_ram_mb": self.timeline_heap_ram,
                "native_ram_mb": self.timeline_native_ram,
                "read_speed_kbps": self.timeline_read_speed_kbps,
                "write_speed_kbps": self.timeline_write_speed_kbps
            }
        }

    def _persist_matrix(self):
        """Exporta o snapshot em disco com séries concatenadas de forma compacta."""
        try:
            safe_target = self.target_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            filename = f"timeline_{int(time.time())}_{safe_target}.json"
            dump_path = self.output_dir / filename
            
            payload = json.dumps(self.report_data, indent=2, cls=CompactSeriesEncoder)
            dump_path.write_text(payload, encoding="utf-8")
            self.report_data["dump_path"] = str(dump_path)
        except Exception:
            pass
            
    def _prune_old_dumps(self):
        """🛑 POLÍTICA DE EXPURGO: Garante no máximo MAX_PERSISTED_DUMPS em disco."""
        try:
            files = sorted(self.output_dir.glob("timeline_*.json"), key=lambda f: f.stat().st_mtime)
            if len(files) > MAX_PERSISTED_DUMPS:
                to_delete = files[:-MAX_PERSISTED_DUMPS]
                for f in to_delete:
                    f.unlink(missing_ok=True)
        except Exception:
            pass

    @classmethod
    def load_last_dump(cls) -> Optional[Dict[str, Any]]:
        """Recupera o último dump gerado no sistema."""
        dump_dir = Path.home() / ".doxoade" / "shadow_profiling"
        if not dump_dir.exists():
            return None
        files = sorted(dump_dir.glob("timeline_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    @classmethod
    def render_data_hud(cls, data: Dict[str, Any], console: Optional[Console] = None):
        """Renderiza o HUD a partir de um dicionário de dados (síncrono ou desserializado)."""
        if not data:
            return

        c = console or Console()
        wall = data.get("wall_time_ms", 0.0)
        hw = data.get("hardware", {})
        cpu = data.get("cpu", {})
        mem = data.get("memory", {})
        disk = data.get("disk", {})
        target = data.get("target", "EXECUÇÃO")

        c.print(f"\n[bold magenta]🦅 SHADOW TIMELINE & FORENSIC MATRIX: {target.upper()}[/bold magenta] "
                f"[dim]({wall:.1f}ms | {hw.get('num_cpus', 1)} CPUs | {hw.get('total_samples', 0)} Amostras a {hw.get('sample_rate_hz', 200)}Hz)[/dim]")

        # 1. Matriz de Recursos Temporais com Densidade CP437
        res_table = Table(box=None, padding=(0, 2), show_header=False)
        res_table.add_column("Recurso", style="bold cyan", width=16)
        res_table.add_column("Ribbon (░▒▓█)", width=28)
        res_table.add_column("Detalhamento de Uso", style="white")

        res_table.add_row(
            "CPU PROCESSO",
            cpu.get("ribbon", ""),
            f"Pico: [bold red]{cpu.get('peak_proc_cpu', 0)}%[/bold red] de 1 Core | Méd: {cpu.get('avg_proc_cpu', 0)}%"
        )
        res_table.add_row(
            "CPU TOTAL (PC)",
            _generate_shaded_ribbon(data.get("series", {}).get("total_cpu_pct", [])),
            f"Pico: [bold yellow]{cpu.get('peak_total_cpu', 0)}%[/bold yellow] da máquina | Méd: {cpu.get('avg_total_cpu', 0)}%"
        )
        res_table.add_row(
            "RAM RSS (TOTAL)",
            mem.get("ribbon_rss", ""),
            f"Início: {mem.get('boot_base_mb', 0)}MB ➔ Pico: [bold green]{mem.get('peak_rss_mb', 0)}MB[/bold green] (Δ {mem.get('delta_mb', 0):+.2f}MB)"
        )
        res_table.add_row(
            "HEAP COMANDO",
            mem.get("ribbon_heap", ""),
            f"Média: [bold yellow]{mem.get('avg_heap_mb', 0)}MB[/bold yellow] | Pico: [bold yellow]{mem.get('peak_heap_mb', 0)}MB[/bold yellow]"
        )
        res_table.add_row(
            "TAXA DISK READ",
            disk.get("ribbon_read_speed", ""),
            f"Pico: [bold cyan]{disk.get('peak_read_speed_kbps', 0)} KB/s[/bold cyan] | Méd: {disk.get('avg_read_speed_kbps', 0)} KB/s"
        )
        res_table.add_row(
            "TAXA DISK WRITE",
            disk.get("ribbon_write_speed", ""),
            f"Pico: [bold magenta]{disk.get('peak_write_speed_kbps', 0)} KB/s[/bold magenta] | Méd: {disk.get('avg_write_speed_kbps', 0)} KB/s"
        )

        c.print(Panel(
            res_table,
            title="[bold magenta]⚡ Consumo de Recursos no Tempo (░ Baixo | ▒ Médio | ▓ Alto | █ Saturado)[/bold magenta]",
            border_style="magenta"
        ))

        # 2. Painel Forense de I/O de Disco
        active_files = disk.get("active_files", [])
        io_files_str = "\n".join([f"    [dim]↳ {f}[/dim]" for f in active_files]) if active_files else "    [dim]Nenhum descritor mantido aberto diretamente[/dim]"
        io_panel_content = (
            f"  [bold]Volume Total Transferido:[/bold]  Lidos: [bold cyan]{disk.get('total_read_mb', 0)} MB[/bold cyan] | "
            f"Gravados: [bold magenta]{disk.get('total_write_mb', 0)} MB[/bold magenta]\n"
            f"  [bold]Operações Físicas (Syscalls):[/bold] [bold cyan]{disk.get('read_ops', 0)}[/bold cyan] Leituras | "
            f"[bold magenta]{disk.get('write_ops', 0)}[/bold magenta] Gravações\n\n"
            f"  [bold yellow]📂 Alvos de I/O Abertos Durante a Execução:[/bold yellow]\n{io_files_str}"
        )
        c.print(Panel(
            io_panel_content,
            title="[bold blue]💾 Diagnóstico Forense de I/O de Disco (Throughput & Syscalls)[/bold blue]",
            border_style="blue"
        ))

        # 3. Decomposição Analítica de Memória RAM
        comp = mem.get("composition_pct", {"boot": 100, "heap": 0, "native": 0})
        comp_bar = _render_composition_bar(comp.get("boot", 0), comp.get("heap", 0), comp.get("native", 0), width=36)
        mem_panel_content = (
            f"  [bold]Distribuição Proporcional Média:[/bold]  {comp_bar}\n\n"
            f"  [bold blue]■ BOOT BASE (Doxoade Core):[/bold blue]  [white]{mem.get('boot_base_mb', 0)} MB[/white] "
            f"[dim]({comp.get('boot', 0)}%) — Carga inicial da VM, Vulcan e subsistemas[/dim]\n"
            f"  [bold yellow]■ HEAP DINÂMICO (Comando):[/bold yellow]   [white]{mem.get('avg_heap_mb', 0)} MB[/white] "
            f"[dim]({comp.get('heap', 0)}%) — Estruturas do algoritmo sob teste (pico: {mem.get('peak_heap_mb', 0)}MB)[/dim]\n"
            f"  [bold cyan]■ CACHES & NATIVOS (C/OS):[/bold cyan]   [white]{mem.get('avg_native_mb', 0)} MB[/white] "
            f"[dim]({comp.get('native', 0)}%) — Páginas SQLite WAL, buffers C e I/O[/dim]"
        )
        c.print(Panel(
            mem_panel_content,
            title="[bold cyan]🧠 Decomposição Estrutural da Memória RAM[/bold cyan]",
            border_style="cyan"
        ))

        # 4. Timeline Cronológica de Fases
        phases = data.get("chrono_phases", [])
        if phases:
            c.print("[bold yellow]⏱️  Evolução Cronológica (Slices Temporais do Processamento):[/bold yellow]")
            phase_lines = []
            for p in phases:
                focus_clean = p['focus'] if p['focus'] != "idle" else "[dim]I/O / SQLite Native Wait / Idle[/dim]"
                phase_lines.append(f"  [cyan]{p['start_ms']:>6.0f}ms - {p['end_ms']:>6.0f}ms[/cyan] ➔ [white bold]{focus_clean}[/white bold]")
            c.print("\n".join(phase_lines))

        # 5. Hotspots e Gargalos de Código
        paths = data.get("hot_paths", [])
        if paths:
            c.print("\n[bold red]🔥 Hotspots e Gargalos de Código Triangulados:[/bold red]")
            t_hot = Table(header_style="bold magenta", border_style="dim white", expand=False)
            t_hot.add_column("Arquivo:Linha", style="cyan", no_wrap=True)
            t_hot.add_column("Função", style="bold yellow")
            t_hot.add_column("Hits", justify="right", style="green")
            t_hot.add_column("% Atividade", justify="right", style="bold red")
            t_hot.add_column("Tempo Est.", justify="right", style="white")
            t_hot.add_column("Média/Hit", justify="right", style="dim white")

            for item in paths:
                t_hot.add_row(
                    f"{item['file']}:{item['line']}",
                    item["func"],
                    str(item["hits"]),
                    f"{item['pct']:.1f}%",
                    f"{item['est_ms']:.1f}ms",
                    f"{item['avg_ms']:.2f}ms"
                )
            c.print(t_hot)

        dump = data.get("dump_path")
        if dump:
            c.print(f"[dim]💾 Dossiê NSR temporal persistido em: {dump}[/dim]\n")

    def render_hud(self, console: Optional[Console] = None):
        """Renderiza a execução atual em andamento."""
        if not self.enabled or not self.report_data:
            return
        self.render_data_hud(self.report_data, console=console)
