# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_lazy.py
"""
Subcomandos de gerenciamento do lazy-loader Vulcan.

  vulcan lazy init    → cria lazy_policy.json e copia lazy_loader.py
  vulcan lazy status  → estado do finder, política ativa e estatísticas
  vulcan lazy add     → adiciona padrão (com validação de módulos protegidos)
  vulcan lazy rm      → remove padrão da política
  vulcan lazy mode    → troca whitelist ↔ blacklist
  vulcan lazy check   → analisa módulo antes de adicionar (SafetyAnalyzer)
  vulcan lazy pause   → suspende intercepcão
  vulcan lazy resume  → retoma intercepcão

Workflow recomendado
--------------------
  1. doxoade vulcan module --path <proj> --auto-main
  2. doxoade vulcan lazy init --path <proj>
  3. doxoade vulcan lazy check engine.thinking.drawer_router --path <proj>
  4. doxoade vulcan lazy add   engine.thinking.drawer_router --save --path <proj>
"""

from __future__ import annotations

import os
import sys
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import _find_project_root


# ── Utilitários internos ──────────────────────────────────────────────────────

def _policy_path(root: str | Path) -> Path:
    return Path(root) / ".doxoade" / "vulcan" / "lazy_policy.json"


def _get_lazy():
    try:
        from doxoade.tools.vulcan import lazy_loader
        return lazy_loader
    except ImportError:
        return None


def _require_lazy(ctx_name: str):
    ll = _get_lazy()
    if ll is None:
        raise click.ClickException(
            f"[{ctx_name}] doxoade.tools.vulcan.lazy_loader não encontrado."
        )
    return ll


def _resolve_root(target_path: str) -> Path:
    return Path(_find_project_root(target_path or os.getcwd()))


def _print_policy_summary(policy, label: str = "Política"):
    pats       = policy.patterns
    mode_color = Fore.YELLOW if policy.mode == "whitelist" else Fore.RED
    click.echo(
        f"  {label} : {mode_color}{policy.mode}{Style.RESET_ALL}  "
        f"│  {len(pats)} padrão(ões)"
    )
    if pats:
        for p in pats:
            click.echo(f"    {Fore.CYAN}• {p}{Style.RESET_ALL}")
    else:
        click.echo(f"    {Style.DIM}(nenhum — nada será interceptado){Style.RESET_ALL}")


def _print_safety_result(result, module_name: str) -> None:
    """Exibe o resultado de SafetyAnalyzer de forma legível."""
    from doxoade.tools.vulcan.lazy_loader import SafetyResult

    if result.level == SafetyResult.SAFE:
        click.echo(
            f"  {Fore.GREEN}✔ SAFE{Style.RESET_ALL}  "
            f"'{module_name}' não tem efeitos colaterais detectados em import-time."
        )
    elif result.level == SafetyResult.WARNING:
        click.echo(
            f"  {Fore.YELLOW}⚠ WARNING{Style.RESET_ALL}  "
            f"'{module_name}' tem padrões que podem causar comportamento inesperado "
            f"se lazy-carregado."
        )
        for r in result.reasons:
            click.echo(f"    {Fore.YELLOW}• {r}{Style.RESET_ALL}")
        click.echo(
            f"\n  {Style.DIM}Você pode adicionar mesmo assim com "
            f"'vulcan lazy add {module_name} --force --save'.{Style.RESET_ALL}"
        )
    else:
        click.echo(
            f"  {Fore.RED}✖ UNSAFE{Style.RESET_ALL}  "
            f"'{module_name}' tem efeitos colaterais em import-time que QUEBRAM se diferidos."
        )
        for r in result.reasons:
            click.echo(f"    {Fore.RED}• {r}{Style.RESET_ALL}")
        click.echo(
            f"\n  {Style.DIM}Não é recomendado adicionar. Use "
            f"'vulcan lazy add {module_name} --force --save' apenas se souber o que está fazendo."
            f"{Style.RESET_ALL}"
        )


# ── Grupo ─────────────────────────────────────────────────────────────────────

@click.group("lazy")
def vulcan_lazy():
    """⚡ Gerencia o sistema de lazy-import e cache do Vulcan."""
    pass


# ── init ──────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("init")
@click.option("--mode", type=click.Choice(["whitelist", "blacklist"]),
              default="whitelist", show_default=True)
@click.option("--patterns", multiple=True, metavar="PATTERN")
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
@click.option("--force", is_flag=True, help="Sobrescreve lazy_policy.json existente.")
def lazy_init(mode, patterns, target_path, force):
    """Inicializa o lazy-loader no projeto alvo.

    \b
    Ações:
      • Cria .doxoade/vulcan/lazy_policy.json  (whitelist vazia = seguro)
      • Copia lazy_loader.py para .doxoade/vulcan/

    O lazy-loader ativa automaticamente via bootstrap Vulcan.
    Nenhum arquivo do projeto alvo é modificado.
    """
    ll   = _require_lazy("lazy init")
    root = _resolve_root(target_path)
    pp   = _policy_path(root)

    if pp.exists() and not force:
        click.echo(
            f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} {pp} já existe. "
            f"Use --force para sobrescrever."
        )
        return

    from doxoade.tools.vulcan.lazy_loader import AccessPolicy
    policy = AccessPolicy(mode=mode, patterns=list(patterns))

    if not ll.save_policy(policy, pp):
        raise click.ClickException(f"Falha ao criar {pp}.")

    click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Política criada em {pp}")
    _print_policy_summary(policy)

    vulcan_dir = root / ".doxoade" / "vulcan"
    if vulcan_dir.exists():
        src = Path(__file__).resolve().parents[1] / "tools" / "vulcan" / "lazy_loader.py"
        dst = vulcan_dir / "lazy_loader.py"
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} lazy_loader.py copiado para {dst}")
        else:
            click.echo(f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} lazy_loader.py não encontrado em {src}")

        click.echo(
            f"\n{Fore.CYAN}[INFO]{Style.RESET_ALL} Próximos passos:\n"
            f"  {Fore.WHITE}doxoade vulcan lazy check <modulo> --path {root}{Style.RESET_ALL}\n"
            f"  {Fore.WHITE}doxoade vulcan lazy add   <modulo> --save --path {root}{Style.RESET_ALL}"
        )
    else:
        click.echo(
            f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Foundry não encontrada. Execute primeiro:\n"
            f"  {Fore.CYAN}doxoade vulcan module --path {root} --auto-main{Style.RESET_ALL}"
        )


# ── check ─────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("check")
@click.argument("module_name")
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
def lazy_check(module_name, target_path):
    """Analisa MODULE_NAME antes de adicionar à política.

    \b
    Verifica três coisas:
      1. Proteção  — está em _NEVER_LAZY ou _NEVER_LAZY_PREFIXES?
                     (será ignorado pelo finder mesmo se adicionado)
      2. Existência — o .py está localizável no ambiente?
      3. Segurança  — tem atexit/signal/thread/meta_path no topo?

    Exemplos:
      doxoade vulcan lazy check re
      doxoade vulcan lazy check engine.thinking.drawer_router
      doxoade vulcan lazy check numpy
    """
    ll   = _require_lazy("lazy check")
    root = _resolve_root(target_path)

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⚡ VULCAN LAZY CHECK — {module_name}{Style.RESET_ALL}\n")

    from doxoade.tools.vulcan.lazy_loader import (
        AccessPolicy, ValidationResult, analyze_module_safety,
    )

    # ── 1. Proteção ───────────────────────────────────────────────────────────
    policy = ll.load_policy(_policy_path(root))
    vr     = policy.validate(module_name)

    if vr.status == ValidationResult.STATUS_PROTECTED:
        click.echo(
            f"  {Fore.RED}✖ PROTEGIDO{Style.RESET_ALL}  {vr.reason}\n"
            f"\n  {Style.DIM}Este módulo NUNCA será interceptado pelo lazy-loader.\n"
            f"  Adicionar à política não tem efeito.{Style.RESET_ALL}\n"
        )
        return

    click.echo(f"  {Fore.GREEN}✔ Não protegido{Style.RESET_ALL}  pode ser interceptado.")

    # ── 2. Segurança ──────────────────────────────────────────────────────────
    click.echo(f"\n  Analisando código-fonte de '{module_name}'...")
    result = analyze_module_safety(module_name, project_root=root) # result = analyze_module_safety(module_name)
    _print_safety_result(result, module_name)

    # ── 3. Resumo ─────────────────────────────────────────────────────────────
    from doxoade.tools.vulcan.lazy_loader import SafetyResult
    click.echo()
    if result.level == SafetyResult.SAFE:
        click.echo(
            f"  {Fore.GREEN}Recomendação: {Style.RESET_ALL}"
            f"seguro para adicionar.\n"
            f"  {Fore.WHITE}doxoade vulcan lazy add {module_name} --save --path {root}{Style.RESET_ALL}"
        )
    elif result.level == SafetyResult.WARNING:
        click.echo(
            f"  {Fore.YELLOW}Recomendação: {Style.RESET_ALL}"
            f"avalie os avisos acima.\n"
            f"  Se confirmar que é seguro:\n"
            f"  {Fore.WHITE}doxoade vulcan lazy add {module_name} --force --save --path {root}{Style.RESET_ALL}"
        )
    else:
        click.echo(
            f"  {Fore.RED}Recomendação: {Style.RESET_ALL}"
            f"NÃO adicionar — efeitos colaterais detectados.\n"
            f"  Se mesmo assim quiser forçar:\n"
            f"  {Fore.WHITE}doxoade vulcan lazy add {module_name} --force --save --path {root}{Style.RESET_ALL}"
        )
    click.echo()


# ── add ───────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("add")
@click.argument("pattern")
@click.option("--save", is_flag=True, help="Persiste em lazy_policy.json.")
@click.option("--force", is_flag=True, help="Ignora avisos de SafetyAnalyzer.")
@click.option("--no-check", is_flag=True, help="Pula análise de segurança.")
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
def lazy_add(pattern, save, force, no_check, target_path):
    """Adiciona PATTERN à política de lazy-import.

    \b
    Por padrão executa SafetyAnalyzer antes de aceitar o padrão.
    Use --force para ignorar avisos (UNSAFE ainda bloqueia sem --force).
    Use --no-check para pular a análise completamente.

    Exemplos de padrões:
      numpy               → 'numpy' e qualquer 'numpy.*'
      pandas.*            → apenas subpacotes (não 'pandas' em si)
      engine.thinking.*   → todos os módulos de engine/thinking/
    """
    ll   = _require_lazy("lazy add")
    root = _resolve_root(target_path)
    pp   = _policy_path(root)

    from doxoade.tools.vulcan.lazy_loader import (
        AccessPolicy, ValidationResult, SafetyResult, analyze_module_safety,
    )

    # ── Verificação de proteção ───────────────────────────────────────────────
    policy = ll.load_policy(pp) if save else AccessPolicy()
    vr     = policy.validate(pattern)

    if vr.status == ValidationResult.STATUS_PROTECTED:
        click.echo(
            f"{Fore.RED}[PROTEGIDO]{Style.RESET_ALL} {vr.reason}\n"
            f"  {Style.DIM}O padrão será salvo no JSON, mas o finder nunca vai interceptar "
            f"este módulo.{Style.RESET_ALL}"
        )
        # Não bloqueia o save — usuário pode querer salvar por documentação,
        # mas avisamos claramente.

    # ── SafetyAnalyzer (pula se padrão tem glob ou --no-check) ───────────────
    has_glob = any(c in pattern for c in ("*", "?", "["))
    if not no_check and not has_glob:
        result = analyze_module_safety(pattern, project_root=root) #result = analyze_module_safety(pattern)
        if result.level == SafetyResult.UNSAFE and not force:
            click.echo(
                f"{Fore.RED}[BLOQUEADO]{Style.RESET_ALL} '{pattern}' tem efeitos colaterais UNSAFE:\n"
            )
            for r in result.reasons:
                click.echo(f"  {Fore.RED}• {r}{Style.RESET_ALL}")
            click.echo(
                f"\n  Use {Fore.WHITE}--force{Style.RESET_ALL} para adicionar mesmo assim, "
                f"ou {Fore.WHITE}vulcan lazy check {pattern}{Style.RESET_ALL} para detalhes."
            )
            return
        if result.level == SafetyResult.WARNING and not force:
            click.echo(
                f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} '{pattern}' tem padrões de risco:"
            )
            for r in result.reasons:
                click.echo(f"  {Fore.YELLOW}• {r}{Style.RESET_ALL}")
            click.echo(
                f"  Use {Fore.WHITE}--force{Style.RESET_ALL} para adicionar mesmo assim."
            )
            return
        if result.level == SafetyResult.SAFE:
            click.echo(f"{Fore.GREEN}[✔ SAFE]{Style.RESET_ALL} Nenhum risco detectado em '{pattern}'.")
    elif has_glob:
        click.echo(
            f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Padrão glob detectado — análise de segurança "
            f"pulada (não é possível resolver globalmente sem importar). "
            f"Use 'vulcan lazy check' em cada módulo concreto."
        )

    # ── Aplica à política live ────────────────────────────────────────────────
    finder = ll.get_finder()
    if finder:
        added = finder.policy.add(pattern)
        msg   = "adicionado à política live" if added else "já existia na política live"
        color = Fore.GREEN if added else Fore.YELLOW
        click.echo(f"{color}[{'OK' if added else 'INFO'}]{Style.RESET_ALL} '{pattern}' {msg}.")

    # ── Persiste ──────────────────────────────────────────────────────────────
    if save:
        disk_policy = ll.load_policy(pp)
        was_new     = disk_policy.add(pattern)
        if ll.save_policy(disk_policy, pp):
            msg = "adicionado e salvo" if was_new else "já existia — arquivo intocado"
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} '{pattern}' {msg} em {pp}.")
        else:
            click.echo(f"{Fore.RED}[ERRO]{Style.RESET_ALL} Falha ao salvar {pp}.")


# ── rm ────────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("rm")
@click.argument("pattern")
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
def lazy_rm(pattern, target_path):
    """Remove PATTERN da política (persiste em lazy_policy.json)."""
    ll   = _require_lazy("lazy rm")
    root = _resolve_root(target_path)
    pp   = _policy_path(root)

    # Live
    finder = ll.get_finder()
    if finder:
        finder.policy.remove(pattern)

    # Disco — sempre
    disk_policy = ll.load_policy(pp)
    was_there   = disk_policy.remove(pattern)
    if ll.save_policy(disk_policy, pp):
        msg   = "removido" if was_there else "não existia na política"
        color = Fore.GREEN if was_there else Fore.YELLOW
        click.echo(f"{color}[{'OK' if was_there else 'INFO'}]{Style.RESET_ALL} '{pattern}' {msg}.")
    else:
        click.echo(f"{Fore.RED}[ERRO]{Style.RESET_ALL} Falha ao salvar {pp}.")


# ── mode ──────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("mode")
@click.argument("mode", type=click.Choice(["whitelist", "blacklist"]))
@click.option("--save", is_flag=True)
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
def lazy_mode(mode, save, target_path):
    """Troca o modo da política (whitelist ↔ blacklist).

    \b
    whitelist  Só os padrões listados são lazy. Vazio = zero intercepcões.
               Mais seguro — recomendado para começar.
    blacklist  Tudo é lazy exceto os padrões. Mais abrangente;
               use quando a whitelist ficar grande demais.
    """
    ll   = _require_lazy("lazy mode")
    root = _resolve_root(target_path)
    pp   = _policy_path(root)

    finder = ll.get_finder()
    if finder:
        finder.policy.mode = mode
        click.echo(
            f"{Fore.GREEN}[OK]{Style.RESET_ALL} "
            f"Modo live → '{Fore.YELLOW}{mode}{Style.RESET_ALL}'."
        )

    if save:
        disk_policy      = ll.load_policy(pp)
        disk_policy.mode = mode
        if ll.save_policy(disk_policy, pp):
            click.echo(
                f"{Fore.GREEN}[OK]{Style.RESET_ALL} "
                f"Modo '{Fore.YELLOW}{mode}{Style.RESET_ALL}' salvo em {pp}."
            )
        else:
            click.echo(f"{Fore.RED}[ERRO]{Style.RESET_ALL} Falha ao salvar {pp}.")


# ── status ────────────────────────────────────────────────────────────────────

@vulcan_lazy.command("status")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--path", "target_path", default=".", type=click.Path(file_okay=False))
def lazy_status(verbose, target_path):
    """Exibe estado do finder, política ativa e estatísticas."""
    ll   = _get_lazy()
    root = _resolve_root(target_path)
    pp   = _policy_path(root)

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⚡ VULCAN LAZY LOADER{Style.RESET_ALL}")

    finder = ll.get_finder() if ll else None

    if finder is None:
        click.echo(
            f"\n  {Fore.YELLOW}● Finder não instalado na sessão atual.{Style.RESET_ALL}\n"
            f"  {Style.DIM}(normal: ativa apenas nos projetos alvo, não no doxoade em si){Style.RESET_ALL}"
        )
    else:
        try:
            pos = next(i for i, f in enumerate(sys.meta_path) if f is finder)
        except StopIteration:
            pos = -1
        state = (
            f"{Fore.GREEN}ATIVO{Style.RESET_ALL}"
            if finder._active
            else f"{Fore.YELLOW}PAUSADO{Style.RESET_ALL}"
        )
        click.echo(f"\n  Finder  : {state}  (sys.meta_path[{pos}])")
        _print_policy_summary(finder.policy, "Política live")

        stats = finder.get_stats()
        if stats:
            n_lazy   = sum(1 for v in stats.values() if not v["loaded"])
            n_loaded = sum(1 for v in stats.values() if v["loaded"])
            total_h  = sum(v["hits"] for v in stats.values())
            click.echo(f"\n  Intercepcões : {len(stats)} módulos")
            click.echo(
                f"   {Fore.YELLOW}Pendentes (lazy): {n_lazy}{Style.RESET_ALL}   "
                f"{Fore.GREEN}Carregados: {n_loaded}{Style.RESET_ALL}   "
                f"Total hits: {total_h}"
            )
            if verbose:
                click.echo(
                    f"\n  {Fore.CYAN}"
                    f"{'Módulo':<45} {'Hits':>5}  {'Defer(ms)':>9}  {'Load(ms)':>8}  Estado"
                    f"{Style.RESET_ALL}"
                )
                click.echo("  " + "─" * 82)
                for name, data in sorted(
                    stats.items(), key=lambda x: x[1]["hits"], reverse=True
                )[:30]:
                    sc    = (
                        f"{Fore.GREEN}loaded{Style.RESET_ALL}"
                        if data["loaded"]
                        else f"{Fore.YELLOW}lazy{Style.RESET_ALL}"
                    )
                    short = (name[:42] + "...") if len(name) > 45 else name
                    click.echo(
                        f"  {short:<45} {data['hits']:>5}  "
                        f"{data['defer_ms']:>9.2f}  "
                        f"{data['load_ms']:>8.2f}  {sc}"
                    )

    click.echo()
    if pp.exists():
        click.echo(f"  {Style.DIM}Política em disco: {pp}{Style.RESET_ALL}")
        if ll:
            _print_policy_summary(ll.load_policy(pp), "Política disco")
    else:
        click.echo(
            f"  {Style.DIM}Sem política em {pp}\n"
            f"  Execute: doxoade vulcan lazy init --path {root}{Style.RESET_ALL}"
        )
    click.echo()


# ── pause / resume ────────────────────────────────────────────────────────────

@vulcan_lazy.command("pause")
def lazy_pause():
    """Suspende intercepcão (finder permanece em sys.meta_path)."""
    ll     = _require_lazy("lazy pause")
    finder = ll.get_finder()
    if finder is None:
        click.echo(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Finder não instalado.")
        return
    finder.pause()
    click.echo(f"{Fore.YELLOW}[PAUSADO]{Style.RESET_ALL} VulcanLazyFinder suspenso.")


@vulcan_lazy.command("resume")
def lazy_resume():
    """Retoma a intercepcão de imports."""
    ll     = _require_lazy("lazy resume")
    finder = ll.get_finder()
    if finder is None:
        click.echo(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Finder não instalado.")
        return
    finder.resume()
    click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} VulcanLazyFinder retomado.")