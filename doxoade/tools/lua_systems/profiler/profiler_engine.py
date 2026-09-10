# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/profiler/profiler_engine.py
""" Motor de Análise de Gargalos e Diagnóstico Empírico de CPU e RAM (Chronos Deep Dissector).
Consome telemetria real de heap e clock exportada pelo Doxly, eliminando médias cegas.
Compliance: ProDeNov 1.2.1, PASC-6. """
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        GREEN = YELLOW = RED = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = RESET_ALL = ""


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

    @classmethod
    def load_boot_report(cls, user_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Lê os dados empíricos de tempo e RAM reais gastos no boot."""
        b_file = cls.get_boot_telemetry_file(user_dir)
        if not b_file.exists():
            return None
        try:
            return json.loads(b_file.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return None

    @classmethod
    def get_live_telemetry(cls, mode: str = "production") -> Optional[Dict[str, Any]]:
        """Lê os dados de runtime do Doxly (FPS real, latência de frame, subsistemas e threads)."""
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
    def render_cli_profile(cls, mode: str = "test") -> None:
        """Renderiza o relatório de alta fidelidade no terminal (Apolo Standard)."""
        from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
        target_dir = (LiteXLEngine.get_user_dir() / ".doxoade" / "test_deploy") if mode == "test" else LiteXLEngine.get_user_dir()

        boot_data = cls.load_boot_report(target_dir)
        live_data = cls.get_live_telemetry(mode=mode)

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"⏱️  CHRONOS PROFILER — RELATÓRIO EMPÍRICO DE ALTA RESOLUÇÃO [{mode.upper()}]")
        print(f"{'═' * 75}{Style.RESET_ALL}\n")

        # 1. Painel de Runtime
        if live_data:
            fps = live_data.get("active_fps", 60.0)
            latency = live_data.get("avg_draw_latency_ms", 0.0)
            ram = live_data.get("gc_memory_kb", 0.0) / 1024.0
            rate = live_data.get("gc_growth_rate_kbs", 0.0)

            fps_col = Fore.GREEN if fps >= 55 else (Fore.YELLOW if fps >= 30 else Fore.RED)
            print(f"  {Fore.WHITE}Taxa de Quadros:{Fore.RESET} {fps_col}{fps:.1f} FPS{Fore.RESET} "
                  f"| {Fore.WHITE}Latência de Frame:{Fore.RESET} {Fore.YELLOW}{latency:.2f}ms{Fore.RESET}")
            print(f"  {Fore.WHITE}Memória Lua (GC):{Fore.RESET} {Fore.CYAN}{ram:.2f} MB{Fore.RESET} "
                  f"| {Fore.WHITE}Taxa de Alocação:{Fore.RESET} {Fore.LIGHTBLACK_EX}{rate:.1f} KB/s{Fore.RESET}\n")

            # Subsistemas gráficos
            subs = live_data.get("subsystems", {})
            if subs:
                print(f"  {Fore.MAGENTA}■ CUSTO REAL POR SUBSISTEMA GRÁFICO (Frame):{Fore.RESET}")
                print(f"    ├─ Abas de Arquivo (Tabs) : {Fore.YELLOW}{subs.get('tabs_avg_ms', 0):.2f}ms{Fore.RESET}")
                print(f"    ├─ Corpo do Código (Doc)  : {Fore.YELLOW}{subs.get('doc_body_avg_ms', 0):.2f}ms{Fore.RESET}")
                print(f"    └─ Marcadores do Gutter   : {Fore.YELLOW}{subs.get('gutter_avg_ms', 0):.2f}ms{Fore.RESET}\n")

            # Corrotinas ativas
            threads = live_data.get("active_threads", {})
            if threads:
                print(f"  {Fore.CYAN}■ CORROTINAS / THREADS ATIVAS (Consumo Acumulado):{Fore.RESET}")
                sorted_th = sorted(threads.items(), key=lambda x: x[1].get("total_ms", 0), reverse=True)
                for tid, st in sorted_th[:6]:
                    print(f"    • {Fore.WHITE}{tid:<30}{Fore.RESET} "
                          f"CPU: {Fore.YELLOW}{st.get('total_ms', 0):.2f}ms{Fore.RESET} "
                          f"({st.get('calls', 0)} calls | pico: {st.get('max_ms', 0):.2f}ms)")
                print()
        else:
            print(f"  {Fore.YELLOW}⚠ Telemetria de runtime pendente (abra o editor para capturar).{Fore.RESET}\n")

        # 2. Ranking Real de Inicialização (Boot Telemetry)
        if boot_data and boot_data.get("modules"):
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
