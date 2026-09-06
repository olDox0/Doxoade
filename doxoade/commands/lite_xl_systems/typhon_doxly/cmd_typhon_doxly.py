# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_doxly/cmd_typhon_doxly.py
# Interface CLI Click (Zeus) integrada ao Doxly
""" Interface CLI Click para o Typhon Doxly Engine (Comandos Zeus).
Disponibiliza: doxoade doxly typhon [tree|probe|chaos|triangulate|report]. """

from __future__ import annotations
import sys
import click
from pathlib import Path

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from .doxly_tree import DOXLY_TREE
from .doxly_probes import run_all_doxly_probes
from .doxly_chaos import run_doxly_chaos_suite
from .doxly_triangulator import DoxlyTriangulator
from .doxly_stress_pack import run_stress_pack


def _resolve_target_dir(mode: str) -> Path:
    """Resolve o USERDIR correspondente ao modo escolhido."""
    from doxoade.commands.lite_xl_systems.typhon_deploy import TyphonDeployEngine
    return TyphonDeployEngine._get_deploy_dir(mode)  # type: ignore


@click.group("typhon", help="🌀 Typhon Doxly — Diagnóstico Vivo, Probes e Triangulação de 3 Vias do Lite XL.")
def typhon_doxly_group():
    """Grupo de comandos Typhon específico para o Lite XL."""
    pass


@typhon_doxly_group.command("tree", help="Exibe a árvore declarativa de falhas do Lite XL.")
@click.option("--compact", "-c", is_flag=True, help="Exibe a árvore em formato compacto.")
def cmd_tree(compact: bool):
    """Renderiza a árvore de componentes e modos de falha catalogados."""
    DOXLY_TREE.print_tree(compact=compact)


@typhon_doxly_group.command("probe", help="Executa probes ativos em runtime (config, APIs, telemetria, logs).")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Modo alvo.")
def cmd_probe(mode: str):
    """Dispara a bateria de detectores vivos contra o ambiente alvo."""
    target_dir = _resolve_target_dir(mode)
    report = run_all_doxly_probes(user_dir=target_dir, verbose=True)
    if not report.is_healthy:
        sys.exit(1)


@typhon_doxly_group.command("chaos", help="Executa a suíte de caos no sandbox para provar sensibilidade dos sensores.")
@click.option("--subsystem", "-s", default=None, help="Filtra por subsistema específico (syntax, render, config, runtime, api_guard).")
def cmd_chaos(subsystem: str | None):
    """Executa a injeção controlada de falhas no sandbox isolado."""
    summary = run_doxly_chaos_suite(verbose=True, filter_subsystem=subsystem)
    if summary["silent"] > 0:
        print(f"{Fore.RED}✖ Falha de cobertura: {summary['silent']} modos de falha silenciosos detectados.{Fore.RESET}")
        sys.exit(1)


@typhon_doxly_group.command("triangulate", help="Executa o censo de 3 vias (Logs + Probes + Caos) com causa raiz e mitigação.")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Modo alvo.")
@click.option("--repair", "-r", is_flag=True, help="Aplica autorreparo automático caso a falha seja auto-fixable.")
@click.option("--chaos", "-c", is_flag=True, help="Verifica sensibilidade contra a suíte de caos.")
def cmd_triangulate(mode: str, repair: bool, chaos: bool):
    """Triangula as 3 vias e sintetiza o veredito final."""
    target_dir = _resolve_target_dir(mode)
    verdict = DoxlyTriangulator.triangulate(
        user_dir=target_dir,
        run_probes=True,
        check_chaos=chaos,
        auto_fix=repair,
    )
    verdict.print_verdict()
    if not verdict.is_healthy and not verdict.auto_repaired:
        sys.exit(1)


@typhon_doxly_group.command("report", help="Relatório consolidado completo (Árvore + Probes + Triangulação).")
@click.option("--mode", "-m", type=click.Choice(["production", "sandbox", "test"]), default="production", help="Modo alvo.")
def cmd_report(mode: str):
    """Gera o dossiê diagnóstico completo."""
    target_dir = _resolve_target_dir(mode)
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 75}")
    print(f"🌀 TYPHON DOXLY FULL DIAGNOSTIC DOSSIER — MODO [{mode.upper()}]")
    print(f"{'=' * 75}{Style.RESET_ALL}")

    # 1. Probes
    probe_report = run_all_doxly_probes(user_dir=target_dir, verbose=True)

    # 2. Triangulação
    verdict = DoxlyTriangulator.triangulate(user_dir=target_dir, run_probes=False)
    verdict.print_verdict()

    if not probe_report.is_healthy or not verdict.is_healthy:
        sys.exit(1)

@typhon_doxly_group.command("chaos", help="Executa a suíte de caos ou o pacote de estresse composto no sandbox.")
@click.option("--subsystem", "-s", default=None, help="Filtra por subsistema específico (syntax, render, config, runtime, api_guard).")
@click.option("--stress", "--pack", is_flag=True, help="Executa o pacote completo de erros propositais compostos.")
def cmd_chaos(subsystem: str | None, stress: bool):
    """Executa a injeção controlada de falhas ou o pacote de estresse composto."""
    if stress:
        report = run_stress_pack(verbose=True)
        if report.crashed > 0 or report.triangulation_accuracy < 80.0:
            sys.exit(1)
        return

    summary = run_doxly_chaos_suite(verbose=True, filter_subsystem=subsystem)
    if summary["silent"] > 0:
        print(f"{Fore.RED}✖ Falha de cobertura: {summary['silent']} modos de falha silenciosos detectados.{Fore.RESET}")
        sys.exit(1)

@typhon_doxly_group.command("fuzz", help="🐺 Executa teste de mutação automática auditando as 5 perguntas (O que, Quem, Onde, Quando, Por que).")
@click.option("--runs", "-n", default=5, help="Número de rodadas de mutação aleatória (Padrão: 5).")
def cmd_fuzz(runs: int):
    """Executa o Fuzzer de mutações e expõe pontos cegos de diagnóstico."""
    from .doxly_mutation_fuzzer import DoxlyMutationFuzzer
    report = DoxlyMutationFuzzer.run_fuzzing_cycle(runs=runs, verbose=True)
    if report.get("blindspots", 0) > 0:
        sys.exit(1)

@typhon_doxly_group.command("struct-audit", help="🏗️ Auditoria estrutural: duplicações e funcionalidades órfãs.")
def cmd_struct_audit():
    """Executa auditoria estrutural sem mutação."""
    from .doxly_structural_fuzzer import DoxlyStructuralFuzzer
    report = DoxlyStructuralFuzzer.run_structural_audit()
    if report.health_score < 80:
        sys.exit(1)


@typhon_doxly_group.command("struct-fuzz", help="🏗️ Fuzzing estrutural: mutações de adição/remoção/alteração.")
@click.option("--runs", "-n", default=10, help="Número de rodadas de mutação estrutural.")
def cmd_struct_fuzz(runs: int):
    """Executa o fuzzer de mutações estruturais avançadas."""
    from .doxly_structural_fuzzer import DoxlyStructuralFuzzer
    report = DoxlyStructuralFuzzer.run_structural_fuzz(runs=runs)
    if report["blindspots"] > 0:
        sys.exit(1)


@typhon_doxly_group.command("struct-chaos", help="🔥 Suíte completa: auditoria + fuzzing estrutural.")
@click.option("--runs", "-n", default=15, help="Número de rodadas de mutação.")
def cmd_struct_chaos(runs: int):
    """Executa a suíte completa de caos estrutural."""
    from .doxly_structural_fuzzer import DoxlyStructuralFuzzer
    result = DoxlyStructuralFuzzer.run_full_chaos_suite(runs=runs)
    if not result["overall_healthy"]:
        sys.exit(1)
